import difflib
import pandas as pd
import re
import unicodedata
from collections import defaultdict
from datetime import time, datetime, date
from django.db.models import Count, Value, Q, F, CharField
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .models import Presenca, PresencaStatus, Situacao, Aluno, Turma, Modalidade, Polo, DiaSemana, TurmaDias, Matricula, Categoria
from apps.pessoas.models import Professor, Estagiario
from django.db.models.functions import Concat
import logging

# Mapeamento de siglas e abreviações extremas
SINONIMOS = {
    'GINÁSTICA ORIENTADA': ['GO'],
    'GINÁSTICA ARTÍSTICA': ['G.A', 'G.ARTISTICA', 'G.ARTITICA', 'G.ARTÍSTICA'],
    'GINÁSTICA FUNCIONAL': ['G.FUNCIONAL'],
    'HIDROGINÁSTICA': ['HIDRO', 'HIDROG'],
    'MUSCULAÇÃO': ['MUSC'],
    'NATAÇÃO': ['NAT'],
    'FUTSAL': ['FUT'],
    'VÔLEI': ['VOLEI'],
    'PILATES': ['PIL'],
}

# Filtro de ruídos comuns
PALAVRAS_RUIDO = [
    'AULA DE ', 'AULAS DE ', 'TURMA DE ', 'TURMA ',
    'INICIANTE', 'AVANÇADO', 'PROF.'
]

logger = logging.getLogger('gestoredu')

def remover_acentos(txt):
    """ Remove acentos, espaços e caracteres especiais (Ex: 'Natação' -> 'NATACAO') """
    if not txt: return ""
    txt = str(txt).strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')

MAPA_SIGLAS = {}
for oficial, lista_ruidos in SINONIMOS.items():
    for ruido in lista_ruidos:
        # A chave fica normalizada (ex: "GA"), mas o valor mantém o nome bonito (ex: "GINÁSTICA ARTÍSTICA")
        MAPA_SIGLAS[remover_acentos(ruido)] = oficial

def get_alunos_em_risco():
    """
    Retorna uma lista de ALUNOS ordenada pela quantidade total de faltas.
    """
    agora = timezone.localtime(timezone.now())
        
    # 1. Busca os dados brutos
    faltas_agrupadas = Presenca.objects.filter(
        status=PresencaStatus.FALTA,
        chamada_id__data_chamada__month=agora.month,
        chamada_id__data_chamada__year=agora.year
    ).values(
        'aluno_id', 
        'aluno_id__primeiro_nome', 
        'aluno_id__ultimo_nome', 
        'chamada_id__turma_id', 
        'chamada_id__turma_id__modalidade_id__nome',
        'chamada_id__turma_id__categoria',
        'chamada_id__turma_id__horario'
    ).annotate(
        total_faltas=Count('id')
    ).filter(
        total_faltas__gte=3
    ).order_by('-total_faltas', 'aluno_id__primeiro_nome')
    
    # Se ninguém faltou
    if not faltas_agrupadas:
        return []

    # 2. Agrupamento por Aluno (coleta apenas os IDs exclusivos usando Set Comprehension para evitar duplicatas)
    aluno_ids = {item['aluno_id'] for item in faltas_agrupadas}
    turma_ids = {item['chamada_id__turma_id'] for item in faltas_agrupadas}
    
    matriculas_ativas = Matricula.objects.filter(
        aluno_id__in = aluno_ids,
        turma_id__in = turma_ids,
        status= Situacao.ATIVA
    ).values_list('aluno_id', 'turma_id', 'id')
    
    # Criação da "Cache L1" em memória usando uma Tabela Hash (Dicionário)
    # Formato: {(aluno_id, turma_id): matricula_id}
    cache_matriculas = {(m[0], m[1]): m[2] for m in matriculas_ativas}
    
    alunos_dict = defaultdict(lambda: {
        'id': None, 
        'nome': '', 
        'sobrenome': '', 
        'turmas_risco': []
    })

    for item in faltas_agrupadas:
        aid = item['aluno_id']
        tid = item['chamada_id__turma_id']

        matricula_id = cache_matriculas.get((aid,tid))

        if matricula_id:
            # Inicializa dados do aluno se primeira vez
            if not alunos_dict[aid]['id']:
                alunos_dict[aid]['id'] = aid
                alunos_dict[aid]['nome'] = item['aluno_id__primeiro_nome']
                alunos_dict[aid]['sobrenome'] = item['aluno_id__ultimo_nome']
            
            # Adiciona os dados desta turma específica na lista do aluno
            alunos_dict[aid]['turmas_risco'].append({
                'turma_id': tid,
                'matricula_id': matricula_id,
                'modalidade': item['chamada_id__turma_id__modalidade_id__nome'],
                'categoria': item['chamada_id__turma_id__categoria'],
                'horario': item['chamada_id__turma_id__horario'],
                'faltas': item['total_faltas']
            })

    # Converte o dicionário de volta para uma lista simples e ordena
    alunos_lista = list(alunos_dict.values())
    alunos_lista.sort(key=lambda aluno: sum(turma['faltas'] for turma in aluno['turmas_risco']), reverse=True)

    return alunos_lista

def get_atestados_vencidos():
    hoje = timezone.localtime(timezone.now()).date()
    
    um_ano_atras = hoje - relativedelta(years=1)
    seis_meses_atras = hoje - relativedelta(months=6)
    
    ANO_MUDANCA_REGRA = 2026
    
    # Cenário 1: Curto-Circuito (Aluno sem nenhum atestado)
    condicao_nulo = Q(questionario_saude__data_atestado_aptidao__isnull=True)
    
    # Cenário 2: Regime Antigo (Tirados ANTES de 2026 -> Valem 6 meses)
    condicao_regra_antiga = Q(
        questionario_saude__data_atestado_aptidao__year__lt=ANO_MUDANCA_REGRA,
        questionario_saude__data_atestado_aptidao__lt=seis_meses_atras
    )
    
    # Cenário 3: Regime Novo (Tirados EM OU DEPOIS de 2026 -> Valem 1 ano)
    condicao_regra_nova = Q(
        questionario_saude__data_atestado_aptidao__year__gte=ANO_MUDANCA_REGRA,
        questionario_saude__data_atestado_aptidao__lt=um_ano_atras
    )
    
    # Alunos ativos cujo atestado é mais antigo que 1 ano OU é nulo
    vencidos = Aluno.objects.filter(
        ativo=True
    ).filter(
        condicao_nulo | condicao_regra_antiga | condicao_regra_nova
    ).select_related(
        'questionario_saude'
    ).order_by(
        'primeiro_nome_limpo', 
        'ultimo_nome_limpo'
    )
    
    return vencidos

def corrigir_nome_modalidade(nome_sujo):
    """
    Tenta corrigir o nome da modalidade usando:
    1. Mapa de Siglas exatas.
    2. Busca por substring na lista de modalidades válidas.
    2. Busca aproximada (Fuzzy) na lista de modalidades válidas.
    """
    if not nome_sujo:
        raise ValueError("O nome da modalidade está vazio na planilha.")
    
    nome_original = str(nome_sujo).strip()
    nome = remover_acentos(nome_original)
    
    # Corta ruído ("AULA DE NATAÇÃO" -> "NATAÇÃO")
    for ruido in PALAVRAS_RUIDO:
        nome = nome.replace(remover_acentos(ruido), '').strip()

    # Verifica Siglas Exatas
    if nome in MAPA_SIGLAS:
        nome = remover_acentos(MAPA_SIGLAS[nome])
    else:
        nome_limpo = nome.replace('.', '').replace(' ', '')
        if nome_limpo in MAPA_SIGLAS:
            nome = remover_acentos(MAPA_SIGLAS[nome_limpo])

    # CONEXÃO EM TEMPO REAL: Busca as modalidades que existem no banco HOJE
    modalidades_banco = Modalidade.objects.values_list('nome', flat=True)
    
    if not modalidades_banco:
        raise ValueError("Erro Crítico: Não há nenhuma modalidade cadastrada no banco de dados ainda.")

    mapa_validas = {remover_acentos(mod): mod for mod in modalidades_banco}
    chaves_validas = list(mapa_validas.keys())

    # Busca Exata Direta
    if nome in mapa_validas:
        return mapa_validas[nome]

    # Varredura por substring (Do maior pro menor para evitar falsos positivos)
    chaves_por_tamanho = sorted(chaves_validas, key=len, reverse=True)
    for chave in chaves_por_tamanho:
        if chave in nome:
            return mapa_validas[chave] 
            
    # Verifica Correção de Texto (Fuzzy Matching a 70%)
    matches = difflib.get_close_matches(nome, chaves_validas, n=1, cutoff=0.7)
    if matches:
        return mapa_validas[matches[0]]
        
    # Subsistema de Sugestões (Fuzzy Matching a 50%)
    sugestoes = difflib.get_close_matches(nome_limpo, chaves_validas, n=1, cutoff=0.5)
    
    if sugestoes:
        sugestao_real = mapa_validas[sugestoes[0]]
        mensagem = f"Erro na planilha: A modalidade '{nome_original}' não existe. Você quis dizer '{sugestao_real}'?"
    else:
        mensagem = f"Erro na planilha: Modalidade '{nome_original}' desconhecida. Nenhuma modalidade similar encontrada no banco de dados."
        
    raise ValueError(mensagem)

def corrigir_nome_polo(nome_planilha):
    """
    Sensor de Aproximação para Polos/Locais.
    Se o usuário esquecer o nome ou digitar uma sigla incompleta, tenta adivinhar.
    """
    if not nome_planilha or str(nome_planilha).strip().lower() in ["", "não informado", "none", "-"]:
        return "POLO NÃO INFORMADO" # Mantém a sua lógica original de fallback

    nome_limpo = str(nome_planilha).strip()

    # 1. Busca Exata
    polo = Polo.objects.filter(nome__iexact=nome_limpo).first()
    if polo:
        return polo.nome

    # 2. Busca por Similaridade (Fuzzy)
    nomes_banco = list(Polo.objects.values_list('nome', flat=True))
    sugestoes = difflib.get_close_matches(nome_limpo, nomes_banco, n=1, cutoff=0.4)
    
    # 3. Disparo do Alerta com Sugestão
    if sugestoes:
        raise ValueError(f"Erro na planilha: O polo/local '{nome_planilha}' não foi encontrado. Você quis dizer '{sugestoes[0]}'?")
    else:
        raise ValueError(f"Erro na planilha: Polo '{nome_planilha}' desconhecido. Verifique o nome correto no sistema.")

def get_valor_seguro(row, col_name):
    """
    Tenta pegar o valor da coluna. Se houver colunas duplicadas com o mesmo nome,
    o Pandas retorna uma Series. Neste caso, pegamos o primeiro valor.
    """
    if col_name not in row.index:
        return None
        
    valor = row[col_name]
    
    # Se for uma Series (duplicata), pega o primeiro item
    if isinstance(valor, pd.Series):
        valor = valor.iloc[0]
        
    return valor

def parse_horario(valor):
    """
    Multiplexador de Tempo: Converte horários de diversas origens 
    (Excel nativo, texto brasileiro, texto americano, abreviações, com pontos) 
    para o objeto datetime.time do Python.
    """
    if not valor:
        return None
        
    # 1. Passa-Banda Nativo (A secretaria formatou a célula corretamente no Excel)
    if isinstance(valor, time):
        return valor
    if isinstance(valor, datetime):
        return valor.time()
        
    # 2. Conversão de Texto Bruto
    texto = str(valor).strip().lower()
    
    # =========================================================================
    # SENSOR REGEX DE ALTA TOLERÂNCIA
    # (\d{1,2})          -> Captura a hora (1 ou 2 dígitos)
    # (?:[:h\.](\d{2}))? -> Captura os minutos (opcional), separador: ':', 'h' ou '.'
    # (?::\d{2})?        -> Ignora os segundos, se o Excel enviar (ex: 14:30:00)
    # (?:\s*([ap]m))?    -> Captura 'am' ou 'pm' (opcional) para o padrão americano
    # =========================================================================
    padrao = r'^(\d{1,2})(?:[:h\.](\d{2}))?(?::\d{2})?(?:\s*([ap]m))?'
    match = re.search(padrao, texto)
    
    if match:
        hora_str, minuto_str, am_pm = match.groups()
        
        try:
            hora = int(hora_str)
            # Se o usuário não digitou os minutos (ex: "14"), assume 0
            minuto = int(minuto_str) if minuto_str else 0
            
            # Ajuste de Clock Americano (AM/PM)
            if am_pm == 'pm' and hora < 12:
                hora += 12
            elif am_pm == 'am' and hora == 12:
                hora = 0
                
            return time(hora, minuto)
        except ValueError:
            # Disjuntor para horas fisicamente impossíveis (ex: 25h99)
            return None
            
    # Se o texto for lixo inconvertível (ex: "A Definir")
    return None
    
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

def get_dias_canonicos(str_dias):
    """
    Retorna 3 valores: (String Formatada, Lista de Enums, Quantidade de Dias)
    """
    
    if not str_dias or pd.isna(str_dias):
        # Retorna 3 valores para não quebrar o unpack
        return "A DEFINIR", [], 0

    s = str(str_dias).upper()
    
    # Detecção
    mapa_dias = {
        DiaSemana.DOMINGO: ["DOM"],
        DiaSemana.SEGUNDA: ["SEG", "2"],
        DiaSemana.TERCA: ["TER", "3"],
        DiaSemana.QUARTA: ["QUA", "4"],
        DiaSemana.QUINTA: ["QUI", "5"],
        DiaSemana.SEXTA: ["SEX", "6"],
        DiaSemana.SABADO: ["SAB", "SÁB"],
    }
    
    dias_enums = {
        dia
        for dia, chaves in mapa_dias.items()
        if any(chave in s for chave in chaves)
    }
    
    if not dias_enums:
        return str_dias, [], 0

    # Ordenação Semanal (Dom -> Sab)
    ordem = {dia: i for i, dia in enumerate(mapa_dias.keys())}
    
    lista_ordenada = sorted(dias_enums, key=lambda d: ordem[d])
    labels = [d.label.upper() for d in lista_ordenada]
    
    # IMPORTANTE: Retorna 3 valores
    return ", ".join(labels), lista_ordenada, len(lista_ordenada)

def corrigir_nome_categoria(nome_planilha):
    """
    Sensor de Aproximação para Categoria.
    Se o usuário esquecer o nome ou digitar uma sigla incompleta, tenta adivinhar.
    """
    if not nome_planilha or str(nome_planilha).strip().lower() in ["", "não informado", "none", "-"]:
        return "CATEGORIA NÃO INFORMADA" # Mantém a sua lógica original de fallback
    
    nome_limpo = str(nome_planilha).strip()
    
    # 1. Busca Exata
    categoria = Categoria.objects.filter(nome__iexact=nome_limpo).first()
    if categoria:
        return categoria.nome
    
    # 2. Busca por Similaridade (Fuzzy)
    nomes_banco = list(Categoria.objects.values_list('nome', flat=True))
    sugestoes = difflib.get_close_matches(nome_limpo, nomes_banco, n=1, cutoff=0.4)
        
    # 3. Disparo do Alerta com Sugestão
    if sugestoes:
        raise ValueError(f"Erro na planilha: A categoria '{nome_planilha}' não foi encontrada. Você quis dizer '{sugestoes[0]}'?")
    else:
        raise ValueError(f"Erro na planilha: Categoria '{nome_planilha}' desconhecida. Verifique o nome correto no sistema.")
    
    

def verifica_se_turma_existe(nome_mod, nome_polo, obj_horario, lista_dias, professores_selecionados, estagiarios_selecionados):
    """
    Sensor de Colisão de Alta Precisão (Impressão Digital Completa).
    Todos os fatores precisam ser EXATAMENTE iguais para ser considerada a mesma turma.
    """
    # 1. Identificação dos nós estruturais (Polo e Modalidade)
    mod = Modalidade.objects.filter(nome__iexact=nome_mod).first()
    if not mod:
        nome_mod_sem = remover_acentos(nome_mod)
        for m in Modalidade.objects.all():
            if remover_acentos(m.nome) == nome_mod_sem:
                mod = m
                break
    
    polo = Polo.objects.filter(nome__iexact=nome_polo).first()
    if not mod or not polo:
        return None

    # 2. Normalização dos Sinais de Entrada (Sets de IDs)
    set_dias_novos = set(lista_dias)
    
    # Filtramos valores vazios para evitar falsos positivos
    ids_profs_novos = set(p.id if hasattr(p, 'id') else int(p) for p in professores_selecionados if p)
    ids_estag_novos = set(e.id if hasattr(e, 'id') else int(e) for e in estagiarios_selecionados if e)

    # 3. Leitura de Candidatas no Barramento
    candidatas = Turma.objects.filter(
        modalidade_id=mod,
        polo_id=polo,
        horario=obj_horario
    ).prefetch_related('dias', 'professores', 'estagiarios')

    # 4. Comparador de Alta Precisão (Porta Lógica AND)
    for cand in candidatas:
        dias_cand = set(d.dia_semana for d in cand.dias.all())
        ids_profs_cand = set(p.id for p in cand.professores.all())
        ids_estag_cand = set(e.id for e in cand.estagiarios.all())
        
        # O disjuntor final: Todos os sets devem ser matematicamente idênticos
        if (dias_cand == set_dias_novos and 
            ids_profs_cand == ids_profs_novos and 
            ids_estag_cand == ids_estag_novos):
            
            return cand.id # Match Perfeito! É exatamente a mesma turma.

    return None # Diferiu em algum ponto (Novo professor, dia ou estagiário). É uma turma NOVA!

def normalizar_merges(ws):
    """
    Garante que o valor de um merged range esteja
    na célula superior esquerda.
    """
    for merge in ws.merged_cells.ranges:
        # célula-mãe
        top_left = ws.cell(row=merge.min_row, column=merge.min_col)

        if top_left.value:
            continue

        # procura valor em qualquer célula do merge
        for row in ws.iter_rows(
            min_row=merge.min_row,
            max_row=merge.max_row,
            min_col=merge.min_col,
            max_col=merge.max_col
        ):
            for cell in row:
                if cell.value:
                    top_left.value = cell.value
                    cell.value = None
                    break
            if top_left.value:
                break

def ler_ficha_chamada(ws):
    """
    Parser Dinâmico de Duas Fases para Planilhas do Excel.
    Sobrevive a alterações de layout, colunas inseridas e rodapés poluídos.
    """
    dados = {
        'modalidade': None, 'local': None, 'horario': None, 
        'dias': None, 'professor': None, 'estagiario': None,
        'categoria': None, 'alunos': []
    }
    
    # SENSOR DE BUSCA HORIZONTAL (Ignora buracos de Merges)
    def extrair_valor_a_direita(linha, col_inicial):
        """ Varre até 5 colunas para a direita procurando o primeiro valor não-vazio """
        for col in range(col_inicial + 1, col_inicial + 6):
            valor = ws.cell(row=linha, column=col).value
            if valor is not None and str(valor).strip() != "":
                return valor
        return None

    # =========================================================================
    # EXTRAÇÃO DE METADADOS (CABEÇALHO ESTÁTICO DO TOPO)
    # =========================================================================
    for row in ws.iter_rows(min_row=1, max_row=15, min_col=1, max_col=25):
        for cell in row:
            valor_celula = str(cell.value).strip().lower() if cell.value else ""
            
            # Usamos o nosso novo sensor para capturar o valor!
            if "modalidade" in valor_celula and not dados['modalidade']:
                dados['modalidade'] = extrair_valor_a_direita(cell.row, cell.column)
            elif "local" in valor_celula and not dados['local']:
                dados['local'] = extrair_valor_a_direita(cell.row, cell.column)
            elif ("horário" in valor_celula or "horario" in valor_celula) and not dados['horario']:
                dados['horario'] = extrair_valor_a_direita(cell.row, cell.column)
            elif "professor" in valor_celula and not dados['professor']:
                dados['professor'] = extrair_valor_a_direita(cell.row, cell.column)
            elif ("estagiário" in valor_celula or "estagiario" in valor_celula) and not dados['estagiario']:
                dados['estagiario'] = extrair_valor_a_direita(cell.row, cell.column)
            elif "categoria" in valor_celula and not dados['categoria']:
                dados['categoria'] = extrair_valor_a_direita(cell.row, cell.column)
            elif "dias" in valor_celula and not dados['dias']:
                texto_original = str(cell.value).strip()
                if len(texto_original) > 6:
                    dados['dias'] = texto_original
                else:
                    dados['dias'] = extrair_valor_a_direita(cell.row, cell.column)

    # =========================================================================
    # FASE 1: CALIBRAÇÃO / MAPEAMENTO DINÂMICO (TABELA DE ALUNOS)
    # =========================================================================
    mapa_colunas = {}
    linha_cabecalho_idx = None
    
    # Dicionário de Sinônimos (Sensibilidade a Variações do Excel)
    termos_num = ['nº', 'n', 'numero', 'número', 'seq', 'ordem']
    termos_nome = ['nome', 'aluno', 'nome do aluno', 'estudante']
    termos_nasc = ['nascimento', 'data nasc', 'dt nasc', 'idade', 'data de nascimento', 'data nascimento']
    termos_atestado = ['atestado', 'validade', 'vencimento', 'atestado médico']

    # Varre as primeiras 30 linhas procurando onde a tabela de alunos começa
    for row in ws.iter_rows(min_row=1, max_row=30):
        mapa_temp = {}
        for cell in row:
            valor = str(cell.value).strip().lower() if cell.value else ""
            if not valor:
                continue
            
            # Identificação por similaridade de String
            if any(t == valor or valor.startswith(t) for t in termos_num) and 'numero' not in mapa_temp:
                mapa_temp['numero'] = cell.column
            elif any(t in valor for t in termos_nome) and 'nome' not in mapa_temp:
                mapa_temp['nome'] = cell.column
            elif any(t in valor for t in termos_nasc) and 'nascimento' not in mapa_temp:
                mapa_temp['nascimento'] = cell.column
            elif any(t in valor for t in termos_atestado) and 'atestado' not in mapa_temp:
                mapa_temp['atestado'] = cell.column

        # O Gatilho: Se achou as colunas Número e Nome, marcamos a linha zero da tabela!
        if 'numero' in mapa_temp and 'nome' in mapa_temp:
            mapa_colunas = mapa_temp
            linha_cabecalho_idx = row[0].row
            logger.info(f"[Scanner Excel] Cabeçalho da tabela localizado na linha {linha_cabecalho_idx}. Mapeamento: {mapa_colunas}")
            break

    # =========================================================================
    # FASE 2: FILTRO POR SYNC WORD E TIPAGEM (EXTRAÇÃO DE ALUNOS)
    # =========================================================================
    if linha_cabecalho_idx and 'numero' in mapa_colunas:
        col_num = mapa_colunas.get('numero')
        col_nome = mapa_colunas.get('nome')
        col_nasc = mapa_colunas.get('nascimento')
        col_atest = mapa_colunas.get('atestado')

        # Começamos a varredura da linha exatamente abaixo do cabeçalho mapeado
        for row_idx in range(linha_cabecalho_idx + 1, ws.max_row + 1):
            
            # Usamos o acesso direto à célula para que a sua função normalizar_merges() faça efeito.
            celula_num = ws.cell(row=row_idx, column=col_num).value
            
            # ---------------------------------------------------------
            # [O INTERTRAVAMENTO] Type Casting = Sync Word
            # Tenta converter a coluna "Nº" para número real. 
            # Se a linha for cabeçalho de rodapé, texto solto, ou em branco, o Python lança erro!
            # ---------------------------------------------------------
            try:
                # Usamos float() dentro de int() caso o Excel mande "1.0"
                num_aluno = int(float(str(celula_num).strip().replace(',', '.')))
            except (ValueError, TypeError):
                # O disjuntor desarmou: Não é um número inteiro válido. 
                # Conclusão: A tabela acabou ou é uma linha de lixo. Pula para a próxima!
                continue
            
            # Se passou do bloco try, o disjuntor está armado: É uma linha de aluno!
            # Captura os dados dinamicamente usando as colunas mapeadas na FASE 1
            nome = ws.cell(row=row_idx, column=col_nome).value if col_nome else None
            nascimento = ws.cell(row=row_idx, column=col_nasc).value if col_nasc else None
            atestado = ws.cell(row=row_idx, column=col_atest).value if col_atest else None
            
            dados['alunos'].append({
                'nome': nome,
                'nascimento': nascimento,
                'atestado': atestado
            })
    else:
        logger.warning("[Scanner Excel] Erro fatal: Tabela de alunos (Colunas Nº e Nome) não encontrada no documento.")

    return dados

def calcular_status_aluno(nome_completo, turma_id=None):
    """
    Retorna o status do aluno com base no banco:
    NOVO | EXISTENTE | ADD_TURMA | MATRICULADO
    """
    # Relé de Proteção contra vácuo: Desarma se o nome não existir
    if not nome_completo or not str(nome_completo).strip():
        return "NÃO IDENTIFICADO", None
    
    parts = str(nome_completo).strip().split()
    p_nome = parts[0]
    u_nome = ' '.join(parts[1:]) if len(parts) > 1 else ''

    aluno = Aluno.objects.filter(
        primeiro_nome__iexact=p_nome,
        ultimo_nome__iexact=u_nome
    ).first()

    if not aluno:
        return 'NOVO', None

    if turma_id:
        if Matricula.objects.filter(
            aluno_id=aluno.id,
            turma_id=turma_id,
            status=Situacao.ATIVA
        ).exists():
            return 'MATRICULADO', aluno
        else:
            return 'ADD_TURMA', aluno

    return 'EXISTENTE', aluno

def rastrear_placas_docentes(valor_celula: str, tipo_componente='professor'):
    """
    Sensor de Varredura Multicanal com Intertravamento Rigoroso:
    Se QUALQUER componente listado na string não for encontrado no banco de dados,
    dispara um curto-circuito (ValueError) abortando toda a importação.
    """
    resultados = []
    
    if not valor_celula or str(valor_celula).strip() in ["", "Não Informado", "-", "None"]:
        return resultados

    # Suporta tanto '/' quanto quebras de linha '\n'
    string_normalizada = str(valor_celula).replace('\n', '/')
    canais_extraidos = [nome.strip() for nome in string_normalizada.split('/') if nome.strip()]
    
    if not canais_extraidos:
        return resultados

    ModeloFisico = Professor if tipo_componente == 'professor' else Estagiario

    for nome_bruto in canais_extraidos:
        nome_limpo = " ".join(nome_bruto.split())
        partes = nome_limpo.split()
        
        if not partes:
            continue
            
        componente_encontrado = None

        # Estágio 1: Encaixe Perfeito
        componente_encontrado = ModeloFisico.objects.annotate(
            nome_completo=Concat('usuario__first_name', Value(' '), 'usuario__last_name', output_field=CharField())
        ).filter(nome_completo__iexact=nome_limpo).first()

        # Estágio 2: Filtro de Extremos
        if not componente_encontrado and len(partes) >= 2:
            componente_encontrado = ModeloFisico.objects.filter(
                usuario__first_name__icontains=partes[0],
                usuario__last_name__icontains=partes[-1]
            ).first()

        # Estágio 3: Sensor de Baixa Resolução
        if not componente_encontrado:
            componente_encontrado = ModeloFisico.objects.filter(
                Q(usuario__first_name__iexact=partes[0]) | Q(usuario__username__iexact=partes[0])
            ).first()

        # DECISÃO DO MÓDULO LOGICO (Relé de Intertravamento)
        if componente_encontrado:
            resultados.append(componente_encontrado)
        else:
            todos_docentes = ModeloFisico.objects.annotate(
                nome_completo=Concat('usuario__first_name', Value(' '), 'usuario__last_name', output_field=CharField())
            ).values_list('nome_completo', flat=True)
            
            # Procura a melhor correspondência com 45% de margem de acerto
            sugestoes = difflib.get_close_matches(nome_limpo, list(todos_docentes), n=1, cutoff=0.45)
            
            titulo = "Professor(a)" if tipo_componente == 'professor' else "Estagiário(a)"
            
            if sugestoes:
                msg_erro = f"Erro na planilha: {titulo} '{nome_limpo}' não encontrado(a). Você quis dizer '{sugestoes[0]}'?"
            else:
                msg_erro = f"Erro na planilha: {titulo} '{nome_limpo}' não existe no sistema. Cadastre-o(a) primeiro."
                
            logger.error(msg_erro)
            raise ValueError(msg_erro)
            
    return resultados

def demultiplexar_docentes_m2m(turma_instancia, valor_celula: str, tipo_componente='professor'):
    """
    Circuito Demux: Lê a célula da planilha, separa as frequências (nomes), 
    localiza os perfis e solda os pinos na placa da Turma de forma Múltipla.
    
    Args:
        turma_instancia: A placa da Turma já criada e salva no banco de dados.
        valor_celula: A string bruta vinda do Excel (ex: "Ricardo Falasque/Leonardo Rosa").
        tipo_componente: 'professor' ou 'estagiario'.
        separador: O caractere que atua como divisor de frequência (padrão '/').
    """
    
    docentes_encontrados = rastrear_placas_docentes(valor_celula, tipo_componente)
    
    for docente in docentes_encontrados:
        if tipo_componente == 'professor':
            turma_instancia.professores.add(docente)
            logger.debug(f"  [+] Professor soldado na turma {turma_instancia.id}")
        elif tipo_componente == 'estagiario':
            turma_instancia.estagiarios.add(docente)
            logger.debug(f"  [+] Estagiário soldado na turma {turma_instancia.id}")