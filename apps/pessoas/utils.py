import pandas as pd
import warnings
import re
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Aluno
from apps.saude.models import QuestionarioSaude
from apps.academico.models import Turma, Matricula, Situacao, Modalidade, Polo
from apps.academico.utils import (
    parse_horario, 
    get_dias_canonicos, 
    corrigir_nome_modalidade, 
    remover_acentos,
    get_valor_seguro
)

def limpar_documento(valor):
    """
    Remove tudo que não é número.
    Aceita strings como '12,345,678', '12.345.678-9', etc.
    """
    if pd.isna(valor): return None
    
    # Converte para string e remove espaços
    str_val = str(valor).strip()
    
    # Remove caracteres comuns de formatação (ponto, traço, vírgula, barra)
    limpo = re.sub(r'[^\d]', '', str_val)
    
    # Filtro básico de sanidade: 
    # RGs podem ser pequenos (ex: 5 dígitos), CPFs têm 11.
    # Se tiver menos que 4 dígitos ou for vazio, ignoramos.
    return limpo if len(limpo) >= 4 else None

def classificar_documento(doc_limpo):
    """
    Decide se é CPF ou RG baseado no tamanho.
    Retorna: ('CPF', valor) ou ('RG', valor) ou (None, None)
    """
    if not doc_limpo:
        return None, None
    
    # CPF tem estritamente 11 dígitos
    if len(doc_limpo) == 11:
        return 'CPF', doc_limpo
    
    # Qualquer outra coisa numérica assumimos que é RG (ou Certidão, etc)
    # RGs geralmente têm entre 5 e 10 dígitos
    return 'RG', doc_limpo

def limpar_cpf(valor):
    """ Remove tudo que não é número e valida tamanho. """
    if pd.isna(valor): return None
    limpo = ''.join(filter(str.isdigit, str(valor)))
    return limpo if len(limpo) == 11 else None

def parse_data(valor):
    """
    Multiplexador de Datas: Converte os objetos do Excel e Strings 
    genéricas em um objeto 'datetime.date' matemático puro.
    """
    if not valor:
        return None
        
    # 1. Passa-Banda Nativo (A secretaria formatou a célula corretamente no Excel)
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
        
    # 2. Conversão de Lixo/Texto (A secretaria digitou numa célula Geral)
    texto = str(valor).strip()
    
    # Filtro: Se o Excel enviou um texto com lixo de relógio (Ex: "2001-04-12 00:00:00")
    if ' ' in texto:
        texto = texto.split()[0]
        
    # Matriz Padrão de tentativas de conversão
    formatos = [
        '%d/%m/%Y', # 12/04/2001
        '%Y-%m-%d', # 2001-04-12
        '%d-%m-%Y', # 12-04-2001
        '%d/%m/%y', # 12/04/01
        '%d.%m.%Y', # 12.04.2001
        '%Y/%m/%d'  # 2001/04/12
    ]
    
    for fmt in formatos:
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
            
    # Disjuntor: Se chegou aqui, a pessoa digitou um texto impossível (Ex: "Não tem")
    return None

def buscar_turma_correspondente(nome_mod, nome_local, obj_horario, str_dias):
    """
    Tenta encontrar uma turma no banco que bata com a descrição do Excel.
    """
    # 1. Busca Modalidade e Polo (Normalizados)
    # Note: Usamos filter().first() para ser tolerante
    # O ideal é que o nome já venha corrigido pela função corrigir_nome_modalidade
    
    # Tenta achar a modalidade pelo nome exato ou corrigido
    mod = Modalidade.objects.filter(nome__iexact=nome_mod).first()
    if not mod:
        # Tenta buscar ignorando acentos (ex: Natação vs Natacao)
        todos_mods = Modalidade.objects.all()
        for m in todos_mods:
            if remover_acentos(m.nome) == remover_acentos(nome_mod):
                mod = m
                break
    polo = Polo.objects.filter(nome__iexact=nome_local).first()

    if not mod or not polo:
        return None, "Modalidade ou Polo não encontrados"# Impossível achar turma sem modalidade ou polo

    # 2. Busca Candidatas por Horário
    candidatas = Turma.objects.filter(
        modalidade_id=mod.id,
        polo_id=polo.id,
        horario=obj_horario
    ).prefetch_related('dias')
    
    if not candidatas.exists():
        return None, f"Nenhuma turma de {nome_mod} às {obj_horario.strftime('%H:%M') if obj_horario is not None else '?'} no polo {polo.nome}"

    # 3. Match Exato de Dias
    # Converte a string "Seg/Qua" do Excel para o set de Enums do sistema
    _, dias_enums_excel, _ = get_dias_canonicos(str_dias)
    set_dias_excel = set(dias_enums_excel)
    
    if not set_dias_excel:
        return None, "Dias não identificados na planilha"

    for turma in candidatas:
        dias_turma = set(turma.dias.values_list('dia_semana', flat=True))
        if dias_turma == set_dias_excel:
            return turma, "OK" # BINGO! Achamos a turma exata.

    # Se chegou aqui, achou horário e modalidade, mas os dias não batem
    return None, f"Dias não batem (Excel: {str_dias})"


def ler_planilha_alunos_preview(arquivo):
    """ Lê a planilha e prepara o preview de Alunos + Matrículas. """
    dados_preview = []
    
    try:
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("ignore")
            # Lê a partir da linha 5 (header=4)
            df = pd.read_excel(arquivo, header=4, dtype=str)

        df.columns = df.columns.str.strip().str.lower()
        
        # Mapa das colunas de turma (até 3 modalidades por aluno)
        grupos_turmas = [
            # 1ª Turma
            {
                'opcoes_mod': ['modalidade 01', 'modalidade 1', 'modalidade'],
                'opcoes_dias': ['dias', 'dia'],
                'opcoes_hora': ['horário', 'horario', 'hora']
            },
            # 2ª Turma (Pandas costuma adicionar .1 se o nome for repetido)
            {
                'opcoes_mod': ['modalidade 02', 'modalidade 2', 'modalidade.1'],
                'opcoes_dias': ['dias.1', 'dias 2', 'dia.1'],
                'opcoes_hora': ['horário.1', 'horario.1', 'hora.1', 'horário 2']
            },
            # 3ª Turma
            {
                'opcoes_mod': ['modalidade 03', 'modalidade 3', 'modalidade.2'],
                'opcoes_dias': ['dias.2', 'dias 3', 'dia.2'],
                'opcoes_hora': ['horário.2', 'horario.2', 'hora.2', 'horário 3']
            }
        ]
        
        col_atestado = next((c for c in df.columns if 'atestado' in c or 'validade' in c), None)

        for index, row in df.iterrows():
            # 1. Dados Pessoais
            nome_completo = str(get_valor_seguro(row, 'nomes') or '').strip()
            # Se não achou 'nomes', tenta 'nome'
            if not nome_completo: 
                nome_completo = str(get_valor_seguro(row, 'nome') or '').strip()

            if not nome_completo or nome_completo.lower() in ['nan', '']:
                continue

            col_doc = next((c for c in df.columns if 'cpf' in c or 'documento' in c or 'rg' in c), None)
            raw_doc = get_valor_seguro(row, col_doc) if col_doc else None
            
            doc_limpo = limpar_documento(raw_doc)
            tipo_doc, valor_doc = classificar_documento(doc_limpo)
            
            cpf_final = valor_doc if tipo_doc == 'CPF' else None
            rg_final = valor_doc if tipo_doc == 'RG' else None
            
            # Validação de documento
            sem_documento = False
            if not cpf_final and not rg_final:
                sem_documento = True
            
            raw_data_nasc = get_valor_seguro(row, 'data nasc.')
            data_nasc = parse_data(raw_data_nasc)
            
            telefone = str(get_valor_seguro(row, 'telefone') or '').strip()
            if telefone.lower() == 'nan': telefone = ""
            
            raw_atestado = get_valor_seguro(row, col_atestado) if col_atestado else None
            data_validade = parse_data(raw_atestado) # Reutilizamos a função de parse de data

            ja_existe = False
            if cpf_final:
                ja_existe = Aluno.objects.filter(cpf=cpf_final).exists()
            elif rg_final:
                # Se não tem CPF, tenta achar pelo RG
                ja_existe = Aluno.objects.filter(rg=rg_final).exists()
            
            # 2. Processar Turmas (Matrículas)
            matriculas_propostas = []
            
            raw_local = get_valor_seguro(row, 'local')
            nome_local = str(raw_local).strip().upper() if pd.notna(raw_local) else 'POLO PRINCIPAL'
            if nome_local.lower() in ['nan', '']: nome_local = 'POLO PRINCIPAL'

            # Loop pelos 3 grupos de turmas possíveis
            for grupo in grupos_turmas:
                # A. Tenta achar a coluna de Modalidade deste grupo
                col_mod_encontrada = None
                for opcao in grupo['opcoes_mod']:
                    if opcao in df.columns:
                        col_mod_encontrada = opcao
                        break
                
                if not col_mod_encontrada:
                    # Se não achou a coluna 'modalidade 02', pula esse grupo
                    continue
                
                # B. Pega o valor
                raw_mod = get_valor_seguro(row, col_mod_encontrada)
                if pd.isna(raw_mod) or str(raw_mod).strip().lower() in ['', 'nan', 'none']:
                    continue

                # C. Acha dias e horário correspondentes
                col_dias = next((op for op in grupo['opcoes_dias'] if op in df.columns), None)
                col_hora = next((op for op in grupo['opcoes_hora'] if op in df.columns), None)

                raw_dias = get_valor_seguro(row, col_dias) if col_dias else None
                raw_hora = get_valor_seguro(row, col_hora) if col_hora else None

                # D. Processamento
                nome_mod = corrigir_nome_modalidade(str(raw_mod))
                obj_horario = parse_horario(raw_hora)
                str_dias = str(raw_dias).strip() if pd.notna(raw_dias) else ""

                # E. Busca no Banco
                turma_encontrada, motivo = buscar_turma_correspondente(nome_mod, nome_local, obj_horario, str_dias)
                
                status_turma = "OK" if turma_encontrada else "ERRO"
                
                horario_fmt = obj_horario.strftime('%H:%M') if obj_horario else '?'
    
                detalhes_str = f"{str_dias} - {horario_fmt}"
                if not turma_encontrada:
                    detalhes_str += f" ({motivo})"

                matriculas_propostas.append({
                    'modalidade': nome_mod,
                    'detalhes': detalhes_str,
                    'turma_id': turma_encontrada.id if turma_encontrada else None,
                    'status': status_turma
                })

            dados_preview.append({
                'temp_id': index,
                'nome': nome_completo,
                'documento': valor_doc or "Sem Doc", # Visualização genérica
                'tipo_doc': tipo_doc,                # 'CPF' ou 'RG'
                'cpf_real': cpf_final,               
                'rg_real': rg_final,         
                'erro_doc': sem_documento,        
                'data_nascimento': data_nasc.strftime('%Y-%m-%d') if data_nasc else None,
                'telefone': telefone,
                'validade_atestado': data_validade.strftime('%Y-%m-%d') if data_validade else None,
                'ja_existe': ja_existe,
                'matriculas': matriculas_propostas
            })

    except Exception as e:
        print(f"ERRO IMPORTAÇÃO ALUNOS: {e}")
        return {'erro': str(e)}
    
    dados_preview.sort(key=lambda x: (
        x['nome'],
    ))

    return dados_preview


def salvar_alunos_confirmados(dados_lista, usuario_responsavel):
    """
    Recebe a lista JSON e salva no banco.
    Retorna dicionário com listas de IDs criados para permitir UNDO.
    """
    resultado = {
        'alunos_criados_ids': [],    # IDs dos alunos novos
        'matriculas_criadas_ids': [], # IDs das matrículas novas
        'count_atualizados': 0,       # Apenas contador (não dá pra desfazer update)
        'atestados': 0
    }
    
    for item in dados_lista:
        # --- TRAVA DE SEGURANÇA ---
        # Se chegou aqui sem nenhum dos dois, pula o registro.
        if not item.get('cpf_real') and not item.get('rg_real'):
            continue
        
        aluno = None
        created_aluno = False
        
        defaults_aluno = {
            'primeiro_nome': item['nome'].split()[0],
            'ultimo_nome': ' '.join(item['nome'].split()[1:]),
            'data_nascimento': item['data_nascimento'],
            'telefone': item['telefone'],
            'ativo': True
        }
        
        # Adiciona RG se existir
        if item.get('rg_real'):
            defaults_aluno['rg'] = item.get('rg_real')

        # 1. SALVAR ALUNO
        if item.get('cpf_real'):
            aluno, created_aluno = Aluno.objects.update_or_create(
                cpf=item['cpf_real'], defaults=defaults_aluno
            )
        elif item.get('rg_real'):
            aluno, created_aluno = Aluno.objects.update_or_create(
                rg=item['rg_real'], defaults=defaults_aluno
            )
        else:
            # Sem doc: Cria sempre
            aluno = Aluno.objects.create(cpf=None, rg=None, **defaults_aluno)
            created_aluno = True

        # Registra ID se foi criado agora
        if created_aluno:
            resultado['alunos_criados_ids'].append(aluno.id)
        else:
            resultado['count_atualizados'] += 1

        if aluno and item.get('validade_atestado'):
            try:
                # Converte string YYYY-MM-DD de volta para objeto date
                data_val_obj = datetime.strptime(item['validade_atestado'], '%Y-%m-%d').date()
                
                # Engenharia Reversa: Se vence em X, foi emitido 6 meses antes
                data_emissao_calculada = data_val_obj - relativedelta(months=6)
                
                # Salva ou Atualiza o Questionário
                QuestionarioSaude.objects.update_or_create(
                    aluno=aluno,
                    defaults={'data_atestado_aptidao': data_emissao_calculada}
                )
                resultado['atestados'] += 1
            except ValueError:
                pass # Ignora se a data estiver inválida

        # 2. SALVAR MATRÍCULAS
        if aluno:
            for mat in item['matriculas']:
                if mat.get('turma_id'):
                    # get_or_create evita duplicatas e nos diz se criou agora
                    matricula_obj, created_mat = Matricula.objects.get_or_create(
                        aluno_id=aluno,
                        turma_id_id=mat['turma_id'],
                        status=Situacao.ATIVA,
                        defaults={
                            'data_inicio': datetime.now().date(),
                            'realizado_por': usuario_responsavel
                        }
                    )
                    
                    if created_mat:
                        resultado['matriculas_criadas_ids'].append(matricula_obj.id)

    return resultado