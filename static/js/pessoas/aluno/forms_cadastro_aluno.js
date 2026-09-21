document.addEventListener('DOMContentLoaded', () => {

    /* ==========================================================================
       1. DEFINIÇÕES GLOBAIS E SELETORES
       ========================================================================== */
    
    // Tenta encontrar os elementos principais de CADA página
    const formCadastroGeral = document.getElementById('aluno-questionario-form');
    const formMatricular = document.getElementById('matricular-aluno-form');
    
    const confirmacaoModalElement = document.getElementById('confirmacaoModal');
    const selecaoTurmasModalElement = document.getElementById('modalSelecaoTurmas');

    /* ==========================================================================
       2. FUNÇÕES HELPER GLOBAIS (Usadas em todas as páginas)
       ========================================================================== */

    /**
     * Adiciona uma mensagem de erro vermelha abaixo do campo (Bootstrap 5).
     */
    function setFieldError(fieldId, message) {
        // Encontra o campo ou o botão (para o modal de turmas)
        const field = document.getElementById(fieldId) || document.querySelector(`[data-bs-target="#${fieldId}"]`);
        if (!field) return;

        field.classList.add('is-invalid');
        
        // Usa 'closest' para encontrar o container e anexar o erro
        const container = field.closest('.mb-3') || field.parentNode;
        let errorDiv = container.querySelector('.invalid-feedback'); // Procura por um existente

        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.id = fieldId + '-error-js'; // ID único para o erro de JS
            errorDiv.className = 'invalid-feedback d-block'; // d-block força a exibição
            container.appendChild(errorDiv); // Anexa ao final do container
        }
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }

    /**
     * Limpa uma mensagem de erro específica.
     */
    function clearFieldError(fieldId) {
        const field = document.getElementById(fieldId) || document.querySelector(`[data-bs-target="#${fieldId}"]`);
        if (!field) return;

        field.classList.remove('is-invalid');
        const errorDiv = document.getElementById(fieldId + '-error-js'); // Procura nosso erro
        if (errorDiv) {
            errorDiv.style.display = 'none';
        }
    }

    /* ==========================================================================
       3. BLOCO: LÓGICA DO FORMULÁRIO DE CADASTRO GERAL (3 ABAS)
       ========================================================================== */
    
    // Este bloco só roda se o form de cadastro E o modal de confirmação existirem
    if (formCadastroGeral && confirmacaoModalElement) {
        
        console.log("Modo: Formulário de Cadastro Geral");

        const confirmacaoModal = new bootstrap.Modal(confirmacaoModalElement);
        const modalBodyConfirmacao = document.getElementById('confirmacaoModalBody');
        const btnConfirmar = document.getElementById('btnConfirmarSalvar');

        // --- Funções Toggle (Mostrar/Esconder) ---
        function toggleOutros(checkboxName, targetDivId) {
            const checkboxes = document.querySelectorAll(`input[name="${checkboxName}"]`);
            const targetDiv = document.getElementById(targetDivId);
            if (!targetDiv) return;
            
            function check() { 
                const show = Array.from(checkboxes).some(c => {
                    if (!c.checked) return false;
                    const labelText = c.nextElementSibling.textContent.trim().toLowerCase();
                    return labelText.includes('outr');
                });
                targetDiv.style.display = show ? 'block' : 'none';
            }
            checkboxes.forEach(cb => cb.addEventListener('change', check));
            check();
        }

        function togglePraticaExercicio() {
            const triggerCheckbox = document.getElementById('id_pratica_exercicio');
            const tipoDiv = document.getElementById('div_id_tipo_exercicio');
            const frequenciaDiv = document.getElementById('div_id_frequencia_exercicio');
            if (!triggerCheckbox || !tipoDiv || !frequenciaDiv) return;
            
            function check() {
                const show = triggerCheckbox.checked;
                tipoDiv.style.display = show ? 'block' : 'none';
                frequenciaDiv.style.display = show ? 'block' : 'none';
            }
            triggerCheckbox.addEventListener('change', check);
            check();
        }
        
        toggleOutros('doencas', 'outras-doencas-div');
        toggleOutros('objetivos', 'outros-objetivos-div');
        togglePraticaExercicio();

        // --- Funções de Validação ---
        function validarLogicaExercicio() {
            const praticaChecked = document.getElementById('id_pratica_exercicio').checked;
            const tipoField = document.getElementById('id_tipo_exercicio');
            const frequenciaField = document.getElementById('id_frequencia_exercicio');
            let isFormValid = true;
            
            if (praticaChecked) {
                if (tipoField.value.trim() === '') {
                    setFieldError('id_tipo_exercicio', 'Por favor, especifique o tipo de exercício.');
                    isFormValid = false;
                } else clearFieldError('id_tipo_exercicio');
                
                if (frequenciaField.value === '') { 
                    setFieldError('id_frequencia_exercicio', 'Por favor, selecione a frequência.');
                    isFormValid = false;
                } else clearFieldError('id_frequencia_exercicio');
            } else {
                clearFieldError('id_tipo_exercicio');
                clearFieldError('id_frequencia_exercicio');
            }
            return isFormValid;
        }

        function validarLogicaOutros() {
            let isFormValid = true;
            
            const doencaCheckboxes = document.querySelectorAll('input[name="doencas"]');
            const outrasDoencasField = document.getElementById('id_outras_doencas');
            const outrasDoencaChecked = Array.from(doencaCheckboxes).some(c => c.checked && c.nextElementSibling.textContent.trim().toLowerCase().includes('outr'));
            
            if (outrasDoencaChecked && outrasDoencasField.value.trim() === '') {
                setFieldError('id_outras_doencas', "Você marcou 'Outra', por favor, especifique a doença.");
                isFormValid = false;
            } else clearFieldError('id_outras_doencas');
            
            const objetivoCheckboxes = document.querySelectorAll('input[name="objetivos"]');
            const outrosObjetivosField = document.getElementById('id_outros_objetivos');
            const outrosObjetivoChecked = Array.from(objetivoCheckboxes).some(c => c.checked && c.nextElementSibling.textContent.trim().toLowerCase().includes('outr'));
            
            if (outrosObjetivoChecked && outrosObjetivosField.value.trim() === '') {
                setFieldError('id_outros_objetivos', "Você marcou 'Outro', por favor, especifique o objetivo.");
                isFormValid = false;
            } else clearFieldError('id_outros_objetivos');
            
            return isFormValid;
        }

        function validarGrupoCheckboxObrigatorio(groupName, containerId, errorMsg) {
            let isGroupValid = true;
            const checks = document.querySelectorAll(`input[name="${groupName}"]`);
            const container = document.getElementById(containerId);
            const errorDivId = `${groupName}-group-error`;
            let errorDiv = document.getElementById(errorDivId);
            
            if (checks.length > 0 && container) {
                const isAnyChecked = Array.from(checks).some(cb => cb.checked);
                if (!isAnyChecked) {
                    isGroupValid = false;
                    checks.forEach(cb => cb.classList.add('is-invalid'));
                    if (!errorDiv) {
                        errorDiv = document.createElement('div');
                        errorDiv.id = errorDivId;
                        errorDiv.className = 'invalid-feedback d-block';
                        const fieldWrapper = container.querySelector('fieldset') || container.querySelector('div'); 
                        if (fieldWrapper) fieldWrapper.parentNode.insertBefore(errorDiv, fieldWrapper.nextSibling);
                        else container.appendChild(errorDiv);
                    }
                    errorDiv.textContent = errorMsg;
                    errorDiv.style.display = 'block';
                } else {
                    checks.forEach(cb => cb.classList.remove('is-invalid'));
                    if (errorDiv) errorDiv.style.display = 'none';
                }
            }
            return isGroupValid;
        }

        function validarCamposSimplesObrigatorios(elementsToValidate) {
            let isFormValid = true;
            elementsToValidate.forEach(input => {
                clearFieldError(input.id);
                let fieldInvalid = false;
                if (input.type === 'checkbox') {
                    if (!input.checked) fieldInvalid = true;
                } else {
                    if (!input.value || input.value.trim() === '') fieldInvalid = true;
                }
                if (fieldInvalid) {
                     setFieldError(input.id, 'Este campo é obrigatório.');
                     isFormValid = false;
                }
            });
            // Removida a lógica antiga de CPF e RG daqui, foi para a validarAbaAluno()
            return isFormValid;
        }
        
        function mostrarAbaComErro() {
           const invalidElements = formCadastroGeral.querySelectorAll(':invalid, .is-invalid');
            if (invalidElements.length > 0) {
                 const firstInvalid = invalidElements[0];
                 const tabPane = firstInvalid.closest('.tab-pane');
                 if (tabPane) {
                     const tabButton = document.querySelector(`[data-bs-target="#${tabPane.id}"]`);
                     if (tabButton) {
                         const tab = new bootstrap.Tab(tabButton);
                         tab.show();
                     }
                 }
            }
        }

        function populateConfirmationModal() {
            let html = '';

            function getLabelFor(elementId) {
                const el = document.getElementById(elementId);
                if (!el) return 'N/A';
                const label = document.querySelector(`label[for="${elementId}"]`);
                return label ? label.textContent.trim() : 'N/A';
            }

            function getValue(elementId) {
                const el = document.getElementById(elementId);
                return el ? el.value : 'N/A';
            }
            
            function getSelectedText(elementId) {
                const select = document.getElementById(elementId);
                if (!select || select.selectedIndex === -1 || !select.value) return "N/A";
                return select.options[select.selectedIndex].text;
            }

            function getCheckedLabels(name) {
                return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`))
                            .map(c => c.nextElementSibling.textContent.trim());
            }

            function formatarData(isoDate) {
                if (!isoDate || isoDate === 'N/A') return "N/A";
                const parts = isoDate.split('-');
                if (parts.length !== 3) return isoDate; 
                return `${parts[2]}/${parts[1]}/${parts[0]}`;
            }

            // Bloco Aluno
            html += '<h4>Dados do Aluno</h4>';
            html += `<p><strong>Nome:</strong> ${getValue('id_nome_completo')}</p>`;
            if (getValue('id_nome_completo_responsavel')) {
                html += `<p><strong>Responsável:</strong> ${getValue('id_nome_completo_responsavel')}</p>`;
            }
            html += `<p><strong>Data de Nasc.:</strong> ${getValue('id_data_nascimento') ? formatarData(getValue('id_data_nascimento')) : "Não preenchida"}</p>`;
            
            // [NOVO] Lógica do Resumo de Documentação
            const isPendente = document.getElementById('id_cadastro_pendente')?.checked;
            if (isPendente) {
                html += `<p><strong>Documentação:</strong> <span class="badge bg-warning text-dark">Cadastro Pendente</span></p>`;
            } else {
                html += `<p><strong>${getSelectedText('id_tipo_documento')}:</strong> ${getValue('id_numero_documento')}</p>`;
            }

            html += `<p><strong>Email:</strong> ${getValue('id_email') ? getValue('id_email') : "Não preenchido"}</p>`;
            html += `<p><strong>Endereço:</strong> ${getValue('id_endereco') ? getValue('id_endereco') : "Não preenchido"}</p>`;
            html += `<p><strong>Telefone:</strong> ${getValue('id_telefone') ? getValue('id_telefone') : "Não preenchido"}</p>`;
            if (getValue('id_telefone_emergencia')) {
                html += `<p><strong>Telefone de Emergência:</strong> ${getValue('id_telefone_emergencia')}</p>`;
            }
            
            // Bloco Questionário e Atestado
            html += '<hr class="my-4">';
            html += '<div class="row">'; // Inicia a malha dividida

            // COLUNA 1: Questionário (Esquerda)
            html += '<div class="col-md-6">';
            html += '<h4 class="mb-3">Questionário de Saúde</h4>';

            html += `<p class="mb-2"><strong>Desmaio ou Vertigens:</strong> ${document.getElementById('id_desmaios_ou_vertigens').checked ? 'Sim' : 'Não'}</p>`;
            
            const doencas = getCheckedLabels('doencas');
            html += `<p class="mb-2"><strong>Doenças:</strong> ${doencas.length > 0 ? doencas.join(', ') : 'Nenhuma'}</p>`;
            const doencasCheckboxes = document.querySelectorAll('input[name="doencas"]');
            const outraDoencaChecked = Array.from(doencasCheckboxes).some(c => c.checked && c.nextElementSibling.textContent.trim().toLowerCase().includes('outr'));
            const outrasDoencasValor = getValue('id_outras_doencas');
            if (outraDoencaChecked && outrasDoencasValor) html += `<p class="mb-2"><strong>Outras Doenças:</strong> ${outrasDoencasValor}</p>`;

            html += `<p class="mb-2"><strong>Histórico cardíaco familiar:</strong> ${document.getElementById('id_historico_cardiaco_familiar').checked ? 'Sim' : 'Não'}</p>`;
            
            if (document.getElementById('id_pratica_exercicio').checked) {
                html += `<p class="mb-2"><strong>Pratica exercícios:</strong> Sim</p>`;
                html += `<p class="mb-2 ms-3 text-muted"><strong>Tipo:</strong> ${getValue('id_tipo_exercicio')}</p>`;
                html += `<p class="mb-2 ms-3 text-muted"><strong>Frequência:</strong> ${getSelectedText('id_frequencia_exercicio')}</p>`;
            } else {
                html += `<p class="mb-2"><strong>Pratica exercícios:</strong> Não</p>`;
            }

            const objetivos = getCheckedLabels('objetivos');
            html += `<p class="mb-2"><strong>Objetivos:</strong> ${objetivos.length > 0 ? objetivos.join(', ') : 'Nenhum'}</p>`;
            const objetivosCheckboxes = document.querySelectorAll('input[name="objetivos"]');
            const outroObjetivoChecked = Array.from(objetivosCheckboxes).some(c => c.checked && c.nextElementSibling.textContent.trim().toLowerCase().includes('outr'));
            const outrosObjetivosValor = getValue('id_outros_objetivos');
            if (outroObjetivoChecked && outrosObjetivosValor) html += `<p class="mb-2"><strong>Outros Objetivos:</strong> ${outrosObjetivosValor}</p>`;

            html += `<p class="mb-0"><strong>Condição especial:</strong> ${document.getElementById('id_declaracao_condicao_especial').checked ? 'Sim' : 'Não'}</p>`;
            html += '</div>'; // Fecha Coluna 1

            // COLUNA 2: Atestado (Direita com borda divisória)
            html += '<div class="col-md-6 border-start">';
            html += '<h4 class="mb-3">Atestado Médico</h4>';
            
            // Lógica de Leitura da Data do Atestado
            const dataAtestadoRaw = document.getElementById('id_data_atestado_aptidao')?.value;
            let dataFormatada = '<span class="badge bg-warning text-dark">Pendente</span>';
            
            if (dataAtestadoRaw) {
                const [ano, mes, dia] = dataAtestadoRaw.split('-');
                dataFormatada = `<span>${dia}/${mes}/${ano}</span>`;
            }
            html += `<p class="mb-3"><strong>Data de Emissão:</strong><span id="confirm-data-atestado">${dataFormatada}</span></p>`;

            // Lógica de Leitura do Arquivo (PDF/Imagem) diretamente da memória do Navegador
            const inputArquivo = document.getElementById('id_arquivo_atestado');
            let arquivoTag = '<span class="badge bg-secondary text-light fw-normal">Nenhum arquivo selecionado</span>';
            
            if (inputArquivo && inputArquivo.files && inputArquivo.files.length > 0) {
                const arquivo = inputArquivo.files[0];
                const nomeArquivo = arquivo.name;
                
                // O PULO DO GATO: Cria uma URL temporária do arquivo que está na memória
                const urlTemporaria = URL.createObjectURL(arquivo);
                
                // Transforma o Badge em um link <a> clicável que abre em nova aba
                arquivoTag = `<a href="${urlTemporaria}" target="_blank" class="badge bg-success text-decoration-none shadow-sm" title="Clique para visualizar o documento">
                    ${nomeArquivo} <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-box-arrow-up-right ms-1 small opacity-75" viewBox="0 0 16 16">
                                        <path fill-rule="evenodd" d="M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 0 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5"/>
                                        <path fill-rule="evenodd" d="M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0z"/>
                                        </svg>
                </a>`;
            }
            
            html += `<p class="mb-0"><strong>Documento Anexo:</strong><br><span id="confirm-arquivo-atestado" class="mt-2 d-inline-block">${arquivoTag}</span></p>`;
            
            html += '</div>'; // Fecha Coluna 2
            html += '</div>'; // Fecha a Linha (Row)

            // Bloco Modalidades
            html += '<hr><h4>Dados da Matrícula(s)</h4>';
            const displayTurmas = document.getElementById('turmas-selecionadas-display').textContent;
            html += `<p><strong>Turmas:</strong> ${displayTurmas}</p>`;

            modalBodyConfirmacao.innerHTML = html;
        }
        
        // --- Lógica dos Botões "Próximo" (só existem nesta página) ---
        const btnProximoAluno = document.getElementById('btn-validar-e-proximo');
        const tabQuestionarioButton = document.getElementById('questionario-tab');
        
        // [NOVO] Tiramos a função de dentro do 'if' para que o evento de 'submit' consiga chamá-la.
        // E atrelamos ela ao 'window' para garantir o acesso global em todas as etapas.
        window.validarAbaAluno = function() { 
            let isAbaValid = true;
            
            // 1. Campos Base (Sempre Obrigatórios)
            const baseInputs = [
                document.getElementById('id_nome_completo'),
            ].filter(el => el !== null);
            
            if (!validarCamposSimplesObrigatorios(baseInputs)) isAbaValid = false;

            // 2. Máquina de Estados: Documentação e Telefones
            const isPendente = document.getElementById('id_cadastro_pendente')?.checked;
            
            const tipoDoc = document.getElementById('id_tipo_documento');
            const numDoc = document.getElementById('id_numero_documento');
            // const nomeResp = document.getElementById('id_nome_completo_responsavel');
            // const telEmergencia = document.getElementById('id_telefone_emergencia');
            // const telAluno = document.getElementById('id_telefone');
            
            // Limpa os erros de todos os campos que mudam de estado
            [tipoDoc, numDoc].forEach(el => {
                if(el) clearFieldError(el.id);
            });

            // Se NÃO for pendente, aplica as regras rigorosas
            if (!isPendente) {
                // Regra 1: Estrutural (Documento é Obrigatório)
                if (!tipoDoc || !tipoDoc.value.trim()) { setFieldError('id_tipo_documento', 'Obrigatório para cadastros completos.'); isAbaValid = false; }
                if (!numDoc || !numDoc.value.trim()) { setFieldError('id_numero_documento', 'Obrigatório para cadastros completos.'); isAbaValid = false; }

                // // Regra 2: Certidão exige responsáveis
                // if (tipoDoc && tipoDoc.value === 'CERTIDAO_NASCIMENTO') {
                //     if (!nomeResp || !nomeResp.value.trim()) { setFieldError('id_nome_completo_responsavel', 'Obrigatório para menores (Certidão).'); isAbaValid = false; }
                //     if (!telEmergencia || !telEmergencia.value.trim()) { setFieldError('id_telefone_emergencia', 'Telefone do responsável é obrigatório.'); isAbaValid = false; }
                // } 
                // // Regra 3: CPF e RG exigem telefone do aluno
                // else if (tipoDoc && (tipoDoc.value === 'CPF' || tipoDoc.value === 'RG')) {
                //     if (!telAluno || !telAluno.value.trim()) { setFieldError('id_telefone', 'Telefone é obrigatório para CPF/RG.'); isAbaValid = false; }
                // }
            }

            return isAbaValid; 
        }
        
        if (btnProximoAluno && tabQuestionarioButton) {
            const tabQuestionario = new bootstrap.Tab(tabQuestionarioButton);

            // [NOVO] Piloto Automático de UI (Melhora a Experiência da Secretaria)
            const tipoDocEl = document.getElementById('id_tipo_documento');
            const pendenteCheckEl = document.getElementById('id_cadastro_pendente');
            
            if (tipoDocEl && pendenteCheckEl) {
                // 1. Se ela selecionar um documento (CPF/RG), nós desmarcamos o Pendente na hora.
                tipoDocEl.addEventListener('change', () => {
                    if (tipoDocEl.value.trim() !== '') {
                        pendenteCheckEl.checked = false;
                    }
                });
                
                // 2. Se ela clicar em Pendente, nós limpamos os campos de documento e os alertas.
                pendenteCheckEl.addEventListener('change', () => {
                    if (pendenteCheckEl.checked) {
                        tipoDocEl.value = '';
                        const numDocEl = document.getElementById('id_numero_documento');
                        if (numDocEl) numDocEl.value = '';
                        
                        window.validarAbaAluno(); // Roda a validação para apagar os traços vermelhos
                    }
                });
            }

            btnProximoAluno.addEventListener('click', () => {
                if (window.validarAbaAluno()) {
                    tabQuestionario.show();
                } else {
                    mostrarAbaComErro(); // Força o foco no erro
                }
            });
        }

        const btnProximoQuestionario = document.getElementById('btn-questionario-proximo');
        const tabAtestadoButton = document.getElementById('atestado-tab'); 
        if (btnProximoQuestionario && tabAtestadoButton) {
           const tabAtestado = new bootstrap.Tab(tabAtestadoButton);
            function validarAbaQuestionario() { // Valida SÓ Aba 2
                let isValid = true;
                const abaQuestionario = document.getElementById('questionario');
                const inputsSimples = abaQuestionario.querySelectorAll(
                    'input[required]:not([name=objetivos]):not([name=doencas]), ' +
                    'select[required]'
                );
                if (!validarCamposSimplesObrigatorios(inputsSimples)) isValid = false;
                if (!validarGrupoCheckboxObrigatorio('objetivos', 'div_id_objetivos', 'Selecione pelo menos um objetivo.')) isValid = false;
                if (!validarLogicaExercicio()) isValid = false;
                if (!validarLogicaOutros()) isValid = false;
                return isValid;
            }
            btnProximoQuestionario.addEventListener('click', () => {
                if (validarAbaQuestionario()) {
                    tabAtestado.show();
                } else {
                    mostrarAbaComErro();
                }
            });
        }

        const btnProximoAtestado = document.getElementById('btn-atestado-proximo');
        const tabModalidadeButton = document.getElementById('modalidade-tab'); 
        
        window.validarAbaAtestado = function() { 
            let isValid = true;
            // O atestado geralmente não é obrigatório no ato da matrícula (pode entregar depois).
            // Mas se for obrigatório no seu sistema, você adiciona o `validarCamposSimplesObrigatorios` aqui.
            return isValid;
        }

        if (btnProximoAtestado && tabModalidadeButton) {
            const tabModalidade = new bootstrap.Tab(tabModalidadeButton);
            
            btnProximoAtestado.addEventListener('click', () => {
                if (window.validarAbaAtestado()) {
                    tabModalidade.show(); // Agora sim, segue para a escolha de Turmas
                } else {
                    mostrarAbaComErro();
                }
            });
        }

        // --- Gatilho Principal "SALVAR" (Formulário de Cadastro) ---
        formCadastroGeral.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Re-valida tudo no momento do envio chamando a função global
            const alunoOk = typeof window.validarAbaAluno === 'function' ? window.validarAbaAluno() : true;
            
            const abaQuestionario = document.getElementById('questionario');
            const inputsQuestionario = abaQuestionario ? abaQuestionario.querySelectorAll('input[required]:not([name=objetivos]):not([name=doencas]), select[required]') : [];
            const questionarioOk = validarCamposSimplesObrigatorios(inputsQuestionario);
            
            const objetivosOk = validarGrupoCheckboxObrigatorio('objetivos', 'div_id_objetivos', 'Selecione pelo menos um objetivo.');
            const exercicioOk = validarLogicaExercicio();
            const outrosOk = validarLogicaOutros();
            const turmasOk = validarSelecaoTurmas(); // Valida o campo escondido
            
            if (alunoOk && questionarioOk && objetivosOk && exercicioOk && outrosOk && turmasOk) {
                populateConfirmationModal();
                confirmacaoModal.show();
            } else {
                mostrarAbaComErro();
            }
        });

        // --- Gatilho do Botão "Confirmar e Salvar" ---
        if (btnConfirmar) { 
            btnConfirmar.addEventListener('click', () => {
                if(confirmacaoModal) confirmacaoModal.hide();
                HTMLFormElement.prototype.submit.call(formCadastroGeral);
            });
        }
    } // --- Fim do Bloco if (formCadastroGeral) ---


    /* ==========================================================================
       4. BLOCO: LÓGICA DO MODAL DE SELEÇÃO DE TURMAS
       ========================================================================== */

    if (selecaoTurmasModalElement) {
        
        const modalBodyTurmas = selecaoTurmasModalElement.querySelector('#lista-turmas-disponiveis');
        const hiddenInputTurmas = document.getElementById('id_turmas_selecionadas_ids');
        const displayDivTurmas = document.getElementById('turmas-selecionadas-display');
        const contadorSpanTurmas = document.getElementById('contador-turmas-selecionadas');
        const btnConfirmarSelecao = document.getElementById('btn-confirmar-selecao-turmas');
        const inputPesquisaTurmas = document.getElementById('input-pesquisa-turmas');

        const MAX_SELECOES = 4;
        let turmasDisponiveis = [];
        let turmasSelecionadasTemp = [];
        let termoBusca = "";

        function getVagasRestantesParaSelecao() {
            if (!hiddenInputTurmas) return 0;
            const matriculasAtuais = parseInt(hiddenInputTurmas.dataset.matriculasAtuais, 10) || 0;
            const vagasNovas = MAX_SELECOES - matriculasAtuais;
            return vagasNovas > 0 ? vagasNovas : 0; 
        }

        function carregarTurmas() {
            try {
                const dataElement = document.getElementById('turmas-data');
                if (dataElement) {
                    const jsonData = dataElement.textContent;
                    if (!jsonData || jsonData.trim() === '') {
                        turmasDisponiveis = [];
                    } else {
                        turmasDisponiveis = JSON.parse(jsonData);
                    }
                } else {
                     turmasDisponiveis = []; 
                }
                renderizarListaTurmas();
            } catch (error) {
                if (modalBodyTurmas) modalBodyTurmas.innerHTML = '<p class="text-danger">Erro ao carregar ou processar dados das turmas.</p>';
            }
        }

        function renderizarListaTurmas() {
            if (!modalBodyTurmas) return;

            const turmasFiltradas = turmasDisponiveis.filter(turma => {
                if (!termoBusca || termoBusca.trim() === "") return true;
                const textoBusca = termoBusca.toLowerCase();
                const dadosParaBuscar = (turma.termo_pesquisa || (turma.nome + " " + turma.detalhes)).toLowerCase();
                return dadosParaBuscar.includes(textoBusca);
            });

            if (turmasFiltradas.length === 0) {
                if (turmasDisponiveis.length === 0) {
                    modalBodyTurmas.innerHTML = '<p>Nenhuma turma com vagas disponível no momento.</p>';
                } else {
                    modalBodyTurmas.innerHTML = '<p class="text-muted text-center my-3">Nenhuma turma encontrada para esta pesquisa.</p>';
                }
                return; 
             }

            const vagasRestantesParaSelecao = getVagasRestantesParaSelecao();

            const grupos = turmasFiltradas.reduce((acc, turma) => {
                const mod = turma.modalidade || "Outras";
                if (!acc[mod]) acc[mod] = [];
                acc[mod].push(turma);
                return acc;
            }, {});

            const accordionId = 'accordionTurmas';
            let html = `<div class="accordion" id="${accordionId}">`;
             
            let index = 0;
            for (const [modalidade, listaTurmas] of Object.entries(grupos)) {
                index++;
                const collapseId = `collapse-${index}`;
                const headingId = `heading-${index}`;
                 
                const isExpanded = (termoBusca !== "") ? "show" : "";
                const isButtonCollapsed = (termoBusca !== "") ? "" : "collapsed";

                html += `
                <div class="accordion-item">
                    <h2 class="accordion-header" id="${headingId}">
                        <button class="accordion-button ${isButtonCollapsed}" type="button" data-bs-toggle="collapse" 
                            data-bs-target="#${collapseId}" aria-expanded="${termoBusca !== ""}" aria-controls="${collapseId}">
                        <strong>${modalidade}</strong> 
                        <span class="badge bg-secondary ms-2">${listaTurmas.length}</span>
                      </button>
                    </h2>
                    <div id="${collapseId}" class="accordion-collapse collapse ${isExpanded}" 
                        aria-labelledby="${headingId}" data-bs-parent="#${accordionId}">
                        <div class="accordion-body p-0">
                            <ul class="list-group list-group-flush">`;

                 listaTurmas.forEach(turma => {
                     const isChecked = turmasSelecionadasTemp.includes(turma.id.toString());
                     const isDisabled = turmasSelecionadasTemp.length >= vagasRestantesParaSelecao && !isChecked;

                    html += `
                        <li class="list-group-item d-flex align-items-start border-0 border-bottom">
                            <div class="form-check me-3 mt-1">
                                <input class="form-check-input" type="checkbox" value="${turma.id}" id="turma-${turma.id}" ${isChecked ? 'checked' : ''} ${isDisabled ? 'disabled' : ''}>
                            </div>
                            <label class="form-check-label flex-grow-1 cursor-pointer" for="turma-${turma.id}">
                                <div class="d-block fw-semibold text-dark">${turma.nome}</div>
                                <div class="text-muted small">
                                    ${turma.detalhes} <span class="badge bg-light text-dark border ms-1">Vagas: ${turma.vagas_restantes}</span>
                                </div>
                            </label>
                        </li>`;
                });

                html += `
                                </ul>
                            </div>
                        </div>
                    </div>`;
             }
             html += `</div>`;

            modalBodyTurmas.innerHTML = html;
            atualizarContador();
            modalBodyTurmas.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                checkbox.addEventListener('change', handleSelecaoTurma);
            });
        }

        function handleSelecaoTurma(event) {
            const checkbox = event.target;
            const turmaId = checkbox.value;
            const vagasRestantesParaSelecao = getVagasRestantesParaSelecao();
            if (checkbox.checked) {
                if (turmasSelecionadasTemp.length < vagasRestantesParaSelecao) {
                    turmasSelecionadasTemp.push(turmaId);
                } else {
                    checkbox.checked = false; 
                }
            } else {
                turmasSelecionadasTemp = turmasSelecionadasTemp.filter(id => id !== turmaId);
            }
            renderizarListaTurmas(); 
        }

        function atualizarContador() {
            if (contadorSpanTurmas) { 
                const matriculasAtuais = parseInt(hiddenInputTurmas.dataset.matriculasAtuais, 10) || 0;
                const totalSelecionadas = matriculasAtuais + turmasSelecionadasTemp.length;
                contadorSpanTurmas.textContent = `${totalSelecionadas} de ${MAX_SELECOES} selecionadas (total)`;
            }
        }
        
        // --- Expondo para o escopo global (para validação do form) ---
        window.validarSelecaoTurmas = function() {
            let isFormValid = true;
            if (!hiddenInputTurmas) return true;

            const idsValue = hiddenInputTurmas.value;
            const turmasContainer = hiddenInputTurmas.closest('.mb-3');
            const errorDivId = 'turmas-group-error';
            let errorDiv = document.getElementById(errorDivId);
            const botaoSelecionar = document.querySelector('[data-bs-target="#modalSelecaoTurmas"]');

            const idsSelecionados = idsValue ? idsValue.split(',') : [];
            const count = idsSelecionados.length;

            let errorMessage = '';
            const isRequired = true;

            if (isRequired && count === 0) {
                errorMessage = 'Selecione pelo menos uma turma clicando no botão.';
                isFormValid = false;
            } else if (count > MAX_SELECOES) {
                errorMessage = `Selecione no máximo ${MAX_SELECOES} turmas (você selecionou ${count}).`;
                isFormValid = false;
            }

            if (!isFormValid) {
                if (botaoSelecionar) botaoSelecionar.classList.add('is-invalid');
                if (!errorDiv) {
                    errorDiv = document.createElement('div');
                    errorDiv.id = errorDivId;
                    errorDiv.className = 'invalid-feedback d-block';
                    if (turmasContainer) turmasContainer.appendChild(errorDiv);
                }
                errorDiv.textContent = errorMessage;
                errorDiv.style.display = 'block';
            } else {
                if (botaoSelecionar) botaoSelecionar.classList.remove('is-invalid');
                if (errorDiv) errorDiv.style.display = 'none';
            }
            return isFormValid;
        }

        selecaoTurmasModalElement.addEventListener('show.bs.modal', () => {
            const idsAtuais = hiddenInputTurmas ? hiddenInputTurmas.value.split(',').filter(id => id) : [];
            turmasSelecionadasTemp = [...idsAtuais]; 

            if (inputPesquisaTurmas) inputPesquisaTurmas.value = "";
            termoBusca = "";

            if (turmasDisponiveis.length === 0) carregarTurmas();
            else renderizarListaTurmas();
        });

        if (inputPesquisaTurmas) {
            inputPesquisaTurmas.addEventListener('input', (e) => {
                termoBusca = e.target.value;
                renderizarListaTurmas();
            });
        }
        
        if (btnConfirmarSelecao) {
            btnConfirmarSelecao.addEventListener('click', () => {
                if(hiddenInputTurmas) hiddenInputTurmas.value = turmasSelecionadasTemp.join(',');
                if (displayDivTurmas) {
                     if (turmasSelecionadasTemp.length > 0) {
                        const nomesSelecionados = turmasDisponiveis
                            .filter(turma => turmasSelecionadasTemp.includes(turma.id.toString()))
                            .map(turma => turma.nome);
                        displayDivTurmas.textContent = `${nomesSelecionados.join(', ')}`;
                    } else {
                        displayDivTurmas.textContent = 'Nenhuma turma selecionada.';
                    }
                }
                if(hiddenInputTurmas) hiddenInputTurmas.dispatchEvent(new Event('change')); 
                const modalInstance = bootstrap.Modal.getInstance(selecaoTurmasModalElement);
                if (modalInstance) modalInstance.hide();
            });
        }
        
    } // --- Fim do Bloco if (selecaoTurmasModalElement) ---


    /* ==========================================================================
       5. BLOCO: LÓGICA DA PÁGINA DE MATRÍCULA AVULSA
       ========================================================================== */

    if (formMatricular) {
        console.log("Modo: Formulário de Matrícula Avulsa");
        formMatricular.addEventListener('submit', function(e) {
            e.preventDefault();
            if (typeof window.validarSelecaoTurmas === 'function' && window.validarSelecaoTurmas()) {
                 HTMLFormElement.prototype.submit.call(formMatricular);
            }
        });
    }

    // RECUPERAÇÃO DE TURMAS
    // Lê se o Django devolveu a tela com alguma turma já checada dentro do modal
    const turmasMarcadas = document.querySelectorAll('#modalSelecaoTurmas input[type="checkbox"]:checked');
    const btnConfirmarTurmas = document.getElementById('btn-confirmar-selecao-turmas');
    
    // Se achou turmas marcadas, "clica" no botão de confirmar silenciosamente 
    // para o seu JS fazer a rotina dele e preencher a aba de modalidades!
    if (turmasMarcadas.length > 0 && btnConfirmarTurmas) {
        btnConfirmarTurmas.click(); 
    }

});