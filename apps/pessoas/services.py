import logging
from django.db import transaction
from django.apps import apps
from django.db.models.fields.related import ForeignKey, ManyToManyField, OneToOneField
from .models import Aluno

logger = logging.getLogger('gestoredu')

@transaction.atomic
def mesclar_cadastros_aluno(id_errado: int, id_correto: int):
    """
    Executa a transferência de barramento entre dois cadastros.
    Usa transação atômica (Interlock): Se um fio falhar na transferência, 
    o sistema dá rollback e desfaz tudo para não corromper o banco.
    """
    if id_errado == id_correto:
        raise ValueError("Curto-circuito: IDs de origem e destino são idênticos.")

    # Utilizamos 'all_with_merged()' para conseguir pegar a placa mesmo se ela já estiver invisível
    aluno_errado = Aluno.objects.all_with_merged().select_for_update().get(id=id_errado)
    aluno_correto = Aluno.objects.all_with_merged().select_for_update().get(id=id_correto)

    logger.info(f"[*] INICIANDO OPERAÇÃO DE MERGE: Transferindo I/O do ID {id_errado} para o ID {id_correto}")

    # =========================================================================
    # VARREDURA UNIVERSAL DE BARRAMENTO (A Mágica da Introspecção do Django)
    # Em vez de escrever 50 linhas de código para cada tabela (Turmas, Presença, Pagamentos),
    # nós usamos o "apps.get_models()" para mapear TODA a infraestrutura do banco.
    # =========================================================================
    for model in apps.get_models():
        for field in model._meta.get_fields():
            
            # Se o campo for uma ligação com o modelo Aluno (ForeignKey, M2M, OneToOne)
            if field.is_relation and field.related_model == Aluno:
                
                # 1. ROTEAMENTO N:1 (Ex: Matricula, Registro de Chamada, Fatura)
                if isinstance(field, ForeignKey) and not isinstance(field, OneToOneField):
                    kwargs_filter = {field.name: aluno_errado}
                    kwargs_update = {field.name: aluno_correto}
                    
                    # Atualiza diretamente via SQL para máxima performance (Batch Update)
                    registros_afetados = model.objects.filter(**kwargs_filter).update(**kwargs_update)
                    if registros_afetados > 0:
                        logger.debug(f"  -> Transferidos {registros_afetados} registros na tabela '{model.__name__}'")

                # 2. ROTEAMENTO N:N (Ex: Turmas onde o aluno participa, se for M2M)
                elif isinstance(field, ManyToManyField):
                    kwargs_filter = {field.name: aluno_errado}
                    objetos_afetados = model.objects.filter(**kwargs_filter)
                    
                    for obj in objetos_afetados:
                        # Extrai o pino M2M físico do objeto
                        m2m_manager = getattr(obj, field.name)
                        # Solda o pino correto e corta o pino errado
                        m2m_manager.add(aluno_correto)
                        m2m_manager.remove(aluno_errado)
                        logger.debug(f"  -> Vínculo M2M alterado no objeto {obj} da tabela '{model.__name__}'")

                # 3. ROTEAMENTO 1:1 (Ex: QuestionarioSaude)
                elif isinstance(field, OneToOneField):
                    kwargs_filter = {field.name: aluno_errado}
                    obj_errado = model.objects.filter(**kwargs_filter).first()
                    
                    if obj_errado:
                        # Para 1:1, precisamos garantir que o Aluno Correto já não tenha esta placa,
                        # caso contrário ocorrerá uma colisão de hardware (Unique Constraint).
                        kwargs_check = {field.name: aluno_correto}
                        if not model.objects.filter(**kwargs_check).exists():
                            setattr(obj_errado, field.name, aluno_correto)
                            obj_errado.save()
                            logger.debug(f"  -> Hardware O2O '{model.__name__}' transferido com sucesso.")
                        else:
                            # Se ambos têm a placa de saúde, priorizamos a do 'correto' e não movemos a errada.
                            logger.warning(f"  -> Colisão de O2O ignorada: O aluno correto já possui a placa '{model.__name__}'.")

    # =========================================================================
    # [PASSO B e C] - CORTE DE ENERGIA E PONTEIRO DE REDIRECIONAMENTO
    # =========================================================================
    logger.info(f"[*] Varredura de tabelas concluída. Desenergizando ID {id_errado}.")
    
    aluno_errado.is_merged = True
    aluno_errado.merged_into = aluno_correto
    
    # Desligando do campo de atividade geral também, para segurança dupla:
    if hasattr(aluno_errado, 'ativo'):
        aluno_errado.ativo = False
        
    aluno_errado.save()

    logger.info(f"[+] Merge executado com sucesso. Aluno {id_errado} agora é um nó fantasma apontando para {id_correto}.")
    return True