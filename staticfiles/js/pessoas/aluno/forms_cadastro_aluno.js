document.addEventListener('DOMContentLoaded', () => {

    const form = document.getElementById('aluno-questionario-form');
    if (!form) {
        console.error("Formulário principal #aluno-questionario-form não encontrado.");
        return;
    } 

    // --- Elementos Comuns ---
    const confirmacaoModalElement = document.getElementById('confirmacaoModal');
    const selecaoTurmasModalElement = document.getElementById('modalSelecaoTurmas');

    // --- Inicialização Modal Confirmação ---
    let confirmacaoModal, modalBodyConfirmacao, btnConfirmar; // Declarar fora
    if (confirmacaoModalElement) {
        confirmacaoModal = new bootstrap.Modal(confirmacaoModalElement);
        modalBodyConfirmacao = document.getElementById('confirmacaoModalBody');
        btnConfirmar = document.getElementById('btnConfirmarSalvar');
    } else {
        console.error("Modal de confirmação #confirmacaoModal não encontrado.");
    }

    // --- Variáveis/Constantes do Modal Seleção Turmas ---
    let modalBodyTurmas, hiddenInputTurmas, displayDivTurmas, contadorSpanTurmas, btnConfirmarSelecao;
    let turmasDisponiveis = [];
    let turmasSelecionadasTemp = [];
    const MAX_SELECOES = 4;

    if (selecaoTurmasModalElement) {
        modalBodyTurmas = selecaoTurmasModalElement.querySelector('#lista-turmas-disponiveis');
        hiddenInputTurmas = document.getElementById('id_turmas_selecionadas_ids');
        displayDivTurmas = document.getElementById('turmas-selecionadas-display');
        contadorSpanTurmas = document.getElementById('contador-turmas-selecionadas');
        btnConfirmarSelecao = document.getElementById('btn-confirmar-selecao-turmas');
    } else {
        console.warn("Modal de seleção de turmas #modalSelecaoTurmas não encontrado (funcionalidade de turma desativada).");
    }

    function toggleOutros(checkboxName, targetDivId) {
        const checkboxes = document.querySelectorAll(`input[name="${checkboxName}"]`);
        const targetDiv = document.getElementById(targetDivId);

        if (!targetDiv) {
            console.error('Elemento-alvo não encontrado:', targetDivId);
            return;
        }

        function check() {
            const show = Array.from(checkboxes).some(c => {
                if (!c.checked) return false;
                
                // Pega o texto da <label> que é o próximo elemento
                const labelText = c.nextElementSibling.textContent.trim().toLowerCase();
                
                // Verifica as variações
                return labelText === 'outro' || labelText === 'outra' || labelText === 'outros' || labelText === 'outras';
            });
            targetDiv.style.display = show ? 'block' : 'none';
        }
        checkboxes.forEach(cb => cb.addEventListener('change', check));
        check(); // Executa ao carregar a página
    }

    function togglePraticaExercicio() {
        // O checkbox gatilho
        const triggerCheckbox = document.getElementById('id_pratica_exercicio');

        // Os alvos (são os 'div_id_*' que o crispy-forms cria)
        const tipoDiv = document.getElementById('div_id_tipo_exercicio');
        const frequenciaDiv = document.getElementById('div_id_frequencia_exercicio');

        // Se não achar os elementos, não faz nada
        if (!triggerCheckbox || !tipoDiv || !frequenciaDiv) {
            console.error('Elementos para toggle de exercício não encontrados.');
            return;
        }

        function check() {
            // Se o gatilho estiver marcado, mostra; senão, esconde.
            const show = triggerCheckbox.checked;
            tipoDiv.style.display = show ? 'block' : 'none';
            frequenciaDiv.style.display = show ? 'block' : 'none';
        }

        triggerCheckbox.addEventListener('change', check);
        check(); // Executa ao carregar a página
    }

    toggleOutros('doencas', 'outras-doencas-div');
    toggleOutros('objetivos', 'outros-objetivos-div');
    togglePraticaExercicio();

    function setFieldError(fieldId, message) {
        const field = document.getElementById(fieldId);
        if (!field) return;

        // Adiciona a borda vermelha do Bootstrap
        field.classList.add('is-invalid');

        // Procura ou cria o <div> de erro
        let errorDiv = document.getElementById(fieldId + '-error');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.id = fieldId + '-error';
            errorDiv.className = 'invalid-feedback';
            
            // Insere o erro logo após o campo
            field.parentNode.insertBefore(errorDiv, field.nextSibling);
        }
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }

    function clearFieldError(fieldId) {
        const field = document.getElementById(fieldId);
        if (!field) return;

        // Remove a borda vermelha
        field.classList.remove('is-invalid');

        const errorDiv = document.getElementById(fieldId + '-error');
        if (errorDiv) {
            errorDiv.style.display = 'none'; // Esconde
        }
    }

    function validarLogicaExercicio() {
        const praticaChecked = document.getElementById('id_pratica_exercicio').checked;
        const tipoField = document.getElementById('id_tipo_exercicio');
        const frequenciaField = document.getElementById('id_frequencia_exercicio');

        let isFormValid = true;

        if (praticaChecked) {
            // Se marcou que pratica, os campos são obrigatórios
            
            if (tipoField.value.trim() === '') {
                setFieldError('id_tipo_exercicio', 'Por favor, especifique o tipo de exercício.');
                isFormValid = false;
            } else {
                clearFieldError('id_tipo_exercicio');
            }

            if (frequenciaField.value === '') { // Para <select>, o "vazio" é ""
                setFieldError('id_frequencia_exercicio', 'Por favor, selecione a frequência.');
                isFormValid = false;
            } else {
                clearFieldError('id_frequencia_exercicio');
            }
        
        } else {
            // Se não marcou, limpa qualquer erro anterior
            clearFieldError('id_tipo_exercicio');
            clearFieldError('id_frequencia_exercicio');
        }
        
        return isFormValid;
    }

    function validarLogicaOutros() {
            let isFormValid = true;

        // Validar "Outras Doenças"
        const doencaCheckboxes = document.querySelectorAll('input[name="doencas"]');
        const outrasDoencasField = document.getElementById('id_outras_doencas');
            
        // Verifica se o checkbox "Outra" está marcado
        const outrasDoencaChecked = Array.from(doencaCheckboxes).some(c => {
            if (!c.checked) return false;
            const labelText = c.nextElementSibling.textContent.trim().toLowerCase();
            // Verifica a raiz 'outr' (pega outro, outra, outros, outras)
            return labelText.includes('outr'); 
        });

        if (outrasDoencaChecked && outrasDoencasField.value.trim() === '') {
            setFieldError('id_outras_doencas', "Você marcou 'Outra', por favor, especifique a doença.");
            isFormValid = false;
        } else {
            clearFieldError('id_outras_doencas');
        }

        // Validar "Outros Objetivos"
        const objetivoCheckboxes = document.querySelectorAll('input[name="objetivos"]');
        const outrosObjetivosField = document.getElementById('id_outros_objetivos');

        // Verifica se o checkbox "Outro" está marcado
        const outrosObjetivoChecked = Array.from(objetivoCheckboxes).some(c => {
            if (!c.checked) return false;
            const labelText = c.nextElementSibling.textContent.trim().toLowerCase();
            return labelText.includes('outr');
        });

        if (outrosObjetivoChecked && outrosObjetivosField.value.trim() === '') {
            setFieldError('id_outros_objetivos', "Você marcou 'Outro', por favor, especifique o objetivo.");
            isFormValid = false;
        } else {
            clearFieldError('id_outros_objetivos');
        }
            
        return isFormValid;
    }

    function validarGruposCheckbox() {
        console.log("--- Iniciando validarGruposCheckbox ---"); // DEBUG
        let isFormValid = true;
        // Validar 'objetivos' (que é obrigatório)
        const objetivosChecks = document.querySelectorAll('input[name="objetivos"]');
        const objetivosContainer = document.getElementById('div_id_objetivos'); // O <div> principal
        console.log("Checkboxes encontrados:", objetivosChecks.length); // DEBUG
        console.log("Container encontrado:", objetivosContainer); // DEBUG

        const errorDivId = 'objetivos-group-error';
        let errorDiv = document.getElementById(errorDivId);
        
        if (objetivosChecks.length > 0 && objetivosContainer) {
            // Verifica se pelo menos um está marcado
            const isObjetivoChecked = Array.from(objetivosChecks).some(cb => cb.checked);
            console.log("Pelo menos um marcado?", isObjetivoChecked); // DEBUG
            
            if (!isObjetivoChecked) {
                console.log(">>> ERRO DETECTADO! Tentando mostrar erro div..."); // DEBUG
                // Se nenhum estiver marcado, é um ERRO
                isFormValid = false;
                
                // Adiciona a classe de erro (borda vermelha) a CADA checkbox
                objetivosChecks.forEach(cb => cb.classList.add('is-invalid'));
                
                // Adiciona a mensagem de erro logo após o <fieldset>
                if (!errorDiv) {
                    errorDiv = document.createElement('div');
                    errorDiv.id = errorDivId;
                    errorDiv.className = 'invalid-feedback d-block'; // Classe de erro do Bootstrap
                    objetivosContainer.appendChild(errorDiv);
                    console.log("Div de erro CRIADA e ANEXADA."); // DEBUG
                } else {
                    console.log("Div de erro já existe."); // DEBUG
                }
                errorDiv.textContent = 'Este campo é obrigatório. Selecione pelo menos um objetivo.';
                errorDiv.style.display = 'block';
                
            } else {
                console.log("Objetivos OK, limpando erros"); // DEBUG
                // Se for válido, limpa os erros
                objetivosChecks.forEach(cb => cb.classList.remove('is-invalid'));
                if (errorDiv) errorDiv.style.display = 'none';  
            }
        }
        
        console.log("--- Fim validarGruposCheckbox, é válido?", isFormValid, "---"); // DEBUG
        return isFormValid;
    }

    function validarCamposObrigatorios() {
        let isFormValid = true;
        
        // Pega todos os inputs obrigatórios que NÃO são checkboxes de grupo
        const inputs = form.querySelectorAll(
            'input[required]:not([name=objetivos]), ' +
            'select[required]'
        );

        inputs.forEach(input => {
            // Limpa erros antigos
            clearFieldError(input.id);

            if (input.type === 'checkbox') {
                if (!input.checked) {
                    setFieldError(input.id, 'Este campo é obrigatório.');
                    isFormValid = false; // Marca o formulário todo como inválido
                }
            } else {
                if (input.value.trim() === '') {
                    setFieldError(input.id, 'Este campo é obrigatório.');
                    isFormValid = false; // Marca o formulário todo como inválido
                }
            }
        });
        
        return isFormValid;
    }

    const btnProximo = document.getElementById('btn-validar-e-proximo');
    const tabQuestionarioButton = document.getElementById('questionario-tab');

    if (btnProximo && tabQuestionarioButton) {
        
        // Prepara o "trocador" de aba do Bootstrap
        const tab = new bootstrap.Tab(tabQuestionarioButton);

        // Função para validar APENAS a aba atual
        function validarAbaAluno() {
            let isTabValid = true;
            const abaAluno = document.getElementById('aluno');
            
            // Pega todos os campos obrigatórios DENTRO da aba 'aluno'
            const inputs = abaAluno.querySelectorAll('input[required], select[required]');

            inputs.forEach(input => {
                if (input.value.trim() === '') {
                    // Usa a sua função 'setFieldError' que já existe
                    setFieldError(input.id, 'Este campo é obrigatório.');
                    isTabValid = false;
                } else {
                    // Usa a sua função 'clearFieldError' que já existe
                    clearFieldError(input.id);
                }
            });
            return isTabValid;
        }

        // Adiciona o gatilho ao clicar
        btnProximo.addEventListener('click', () => {
            if (validarAbaAluno()) {
                // Se a Aba 1 for válida, troca para a Aba 2
                tab.show();
            }
        });
    }

    const btnProximoQuestionario = document.getElementById('btn-questionario-proximo');
    const tabModalidadeButton = document.getElementById('modalidade-tab'); 

    if (btnProximoQuestionario && tabModalidadeButton) {
        const tabModalidade = new bootstrap.Tab(tabModalidadeButton);
        
        btnProximoQuestionario.addEventListener('click', () => {
            // Chama as validações JS da Aba 2
            const gruposValid = validarGruposCheckbox(); // Valida 'objetivos'
            const exercicioValid = validarLogicaExercicio(); // Valida tipo/frequencia
            const outrosValid = validarLogicaOutros(); // Valida 'outros' se marcado
            const aptidaoChecked = validarCamposObrigatorios(); // Valida aptidao
            

            // Verifica se TODAS as validações da Aba 2 passaram
            if (gruposValid && exercicioValid && outrosValid && aptidaoChecked) {
                tabModalidade.show(); // Se for válido, vai para a Aba 3
            } else {
                // Se for inválido, apenas chama mostrarAbaComErro para focar no erro
                console.log("Validação JS da Aba 2 falhou.");
                mostrarAbaComErro(); 
            }
        });
    }

    // --- 1. Função para buscar/carregar dados das turmas ---
    async function carregarTurmas() {
        try {
            const dataElement = document.getElementById('turmas-data');
            if (dataElement) {
                turmasDisponiveis = JSON.parse(dataElement.textContent);
                console.log("Turmas carregadas do HTML:", turmasDisponiveis); // DEBUG
            } else {
                 console.error("Script tag #turmas-data não encontrada no HTML.");
                 turmasDisponiveis = []; 
            }
            
            renderizarListaTurmas();
        } catch (error) {
            console.error("Erro ao carregar turmas:", error);
            modalBodyTurmas.innerHTML = '<p class="text-danger">Erro ao carregar turmas.</p>';
        }
    }

    // --- 2. Função para renderizar a lista no modal ---
    function renderizarListaTurmas() {
        if (!turmasDisponiveis || turmasDisponiveis.length === 0) {
            modalBodyTurmas.innerHTML = '<p>Nenhuma turma com vagas disponível no momento.</p>';
            return;
        }

        let html = '<ul class="list-group">'; // Ou use uma tabela
        turmasDisponiveis.forEach(turma => {
            // Verifica se esta turma já estava selecionada (ao reabrir o modal)
            const isChecked = turmasSelecionadasTemp.includes(turma.id.toString());
            // Desabilita se o limite foi atingido e ela não está marcada
            const isDisabled = turmasSelecionadasTemp.length >= MAX_SELECOES && !isChecked;

            html += `
                <li class="list-group-item">
                    <input class="form-check-input me-2" type="checkbox" 
                           value="${turma.id}" 
                           id="turma-${turma.id}" 
                           ${isChecked ? 'checked' : ''}
                           ${isDisabled ? 'disabled' : ''}
                           aria-label="Selecionar ${turma.nome}">
                    <label class="form-check-label stretched-link" for="turma-${turma.id}">
                        <strong>${turma.nome}</strong> 
                        <small class="text-muted d-block">
                            ${turma.detalhes || ''} Vagas: ${turma.vagas_restantes || '?'} 
                        </small> 
                    </label>
                </li>`;
        });
        html += '</ul>';
        modalBodyTurmas.innerHTML = html;
        atualizarContador();

        // Adiciona listeners aos checkboxes recém-criados
        modalBodyTurmas.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', handleSelecaoTurma);
        });
    }

    // --- 3. Função para lidar com a seleção/desseleção ---
    function handleSelecaoTurma(event) {
        const checkbox = event.target;
        const turmaId = checkbox.value;

        if (checkbox.checked) {
            if (turmasSelecionadasTemp.length < MAX_SELECOES) {
                turmasSelecionadasTemp.push(turmaId);
            } else {
                checkbox.checked = false; // Impede a seleção acima do limite
                // Pode adicionar um alerta visual aqui
                console.warn(`Limite de ${MAX_SELECOES} turmas atingido.`);
            }
        } else {
            turmasSelecionadasTemp = turmasSelecionadasTemp.filter(id => id !== turmaId);
        }
        
        // Re-renderiza a lista para habilitar/desabilitar checkboxes
        renderizarListaTurmas(); 
    }

    // --- 4. Função para atualizar o contador visual ---
    function atualizarContador() {
        if (contadorSpanTurmas) { 
            contadorSpanTurmas.textContent = `${turmasSelecionadasTemp.length} de ${MAX_SELECOES} selecionadas`;
        } else {
            // Loga um aviso se o elemento do contador não foi encontrado
            console.warn("Elemento contador (#contador-turmas-selecionadas) não encontrado no modal.");
        }
    }

    // --- 5. Ação ao abrir o modal ---
    if (selecaoTurmasModalElement) {
        selecaoTurmasModalElement.addEventListener('show.bs.modal', () => {
            // Pega os IDs já selecionados (do input hidden) e guarda temporariamente
            // Garante que hiddenInputTurmas existe antes de acessar .value
            const idsAtuais = hiddenInputTurmas ? hiddenInputTurmas.value.split(',').filter(id => id) : [];
            turmasSelecionadasTemp = [...idsAtuais]; // Copia para a variável temporária
        
            // Carrega/Renderiza a lista (se ainda não carregou)
            if (turmasDisponiveis.length === 0) {
                carregarTurmas();
            } else {
                renderizarListaTurmas(); // Apenas re-renderiza com o estado atual
            }
        });
    }

    // --- 6. Ação ao clicar em "Confirmar Seleção" ---
    if (btnConfirmarSelecao) {
        btnConfirmarSelecao.addEventListener('click', () => {
            // Atualiza o input hidden com os IDs selecionados no modal
             if(hiddenInputTurmas) hiddenInputTurmas.value = turmasSelecionadasTemp.join(','); // Verifica se existe
            
            // Atualiza o display no formulário principal (opcional)
             if (displayDivTurmas) { // Verifica se existe
                 if (turmasSelecionadasTemp.length > 0) {
                    const nomesSelecionados = turmasDisponiveis
                        .filter(turma => turmasSelecionadasTemp.includes(turma.id.toString()))
                        .map(turma => turma.nome);
                    displayDivTurmas.textContent = `${nomesSelecionados.join(', ')}`;
                } else {
                    displayDivTurmas.textContent = 'Nenhuma turma selecionada.';
                }
             }
            
            // Dispara um evento 'change' no hidden input para validações JS, se necessário
            if(hiddenInputTurmas) hiddenInputTurmas.dispatchEvent(new Event('change')); 

            // Fecha o modal
            // Verifica se o elemento do modal existe antes de tentar pegar a instância
            if (selecaoTurmasModalElement) { 
                const modalInstance = bootstrap.Modal.getInstance(selecaoTurmasModalElement); // <-- CORRIGIDO AQUI
                if (modalInstance) modalInstance.hide(); // Verifica se a instância foi encontrada
            }
        });
    }

    function validarSelecaoTurmas() {
        let isFormValid = true;
        // Certifique-se que hiddenInputTurmas foi encontrado no início
        if (!hiddenInputTurmas) return true; // Se o modal não existe, não valida

        const idsValue = hiddenInputTurmas.value;
        const turmasContainer = hiddenInputTurmas.closest('.mb-3'); // Pega o container do botão/display
        const errorDivId = 'turmas-group-error';
        let errorDiv = document.getElementById(errorDivId);
        const botaoSelecionar = document.querySelector('[data-bs-target="#modalSelecaoTurmas"]'); // Botão

        const idsSelecionados = idsValue ? idsValue.split(',') : [];
        const count = idsSelecionados.length;

        let errorMessage = '';
        const isRequired = true; // Defina como true se for obrigatório

        if (isRequired && count === 0) {
            errorMessage = 'Selecione pelo menos uma turma clicando no botão.';
            isFormValid = false;
        } else if (count > MAX_SELECOES) { // Usa a constante
            errorMessage = `Selecione no máximo ${MAX_SELECOES} turmas (você selecionou ${count}).`;
            isFormValid = false;
        }

        // --- Exibir/Limpar Erro ---
        if (!isFormValid) {
            if (botaoSelecionar) botaoSelecionar.classList.add('is-invalid'); // Marca o botão
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.id = errorDivId;
                errorDiv.className = 'invalid-feedback d-block';
                if (turmasContainer) turmasContainer.appendChild(errorDiv); // Anexa ao container
            }
            errorDiv.textContent = errorMessage;
            errorDiv.style.display = 'block';
        } else {
             if (botaoSelecionar) botaoSelecionar.classList.remove('is-invalid'); // Limpa o botão
            if (errorDiv) errorDiv.style.display = 'none';
        }
        return isFormValid;
    }

    function mostrarAbaComErro() {
        const invalidElements = form.querySelectorAll(':invalid, .is-invalid');

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

        // --- Helper para pegar o texto da label de um checkbox/radio
        function getLabelFor(elementId) {
            const el = document.getElementById(elementId);
            if (!el) return 'N/A';
            // Pega a <label> associada ao campo
            const label = document.querySelector(`label[for="${elementId}"]`);
            return label ? label.textContent.trim() : 'N/A';
        }

        // --- Helper para pegar o valor de um campo de texto
        function getValue(elementId) {
            const el = document.getElementById(elementId);
            return el ? el.value : 'N/A';
        }
        
        // --- Helper para pegar o TEXTO de uma opção de <select>
        function getSelectedText(elementId) {
            const select = document.getElementById(elementId);
            if (!select || select.selectedIndex === -1) return "Nenhuma";
            return select.options[select.selectedIndex].text;
        }

        // --- Helper para pegar os labels dos checkboxes marcados
        function getCheckedLabels(name) {
            return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`))
                        .map(c => c.nextElementSibling.textContent.trim());
        }

        // --- Helper para formatar datas "YYYY-MM-DD" para "DD/MM/YYYY"
        function formatarData(isoDate) {
            if (!isoDate || isoDate === 'N/A') {
                return "N/A"; // Retorna se a data estiver vazia
            }
            // A data vem do input como "YYYY-MM-DD"
            const parts = isoDate.split('-');
            if (parts.length !== 3) {
                return isoDate; // Retorna o valor original se não for o formato esperado
            }
            // Reorganiza para "DD/MM/YYYY"
            return `${parts[2]}/${parts[1]}/${parts[0]}`;
        }

        // --- HTML do Resumo ---
        
        // Bloco Aluno
        html += '<h4>Dados do Aluno</h4>';
        html += `<p><strong>Nome:</strong> ${getValue('id_nome_completo')}</p>`;
        if (getValue('id_nome_completo_responsavel')) {
            html += `<p><strong>Nome do Responsável:</strong> ${getValue('id_nome_completo_responsavel')}</p>`;
        }
        html += `<p><strong>Data de Nasc.:</strong> ${formatarData(getValue('id_data_nascimento'))}</p>`;
        html += `<p><strong>RG:</strong> ${getValue('id_rg')}</p>`;
        html += `<p><strong>CPF:</strong> ${getValue('id_cpf')}</p>`;
        html += `<p><strong>Email:</strong> ${getValue('id_email')}</p>`;
        html += `<p><strong>Endereço:</strong> ${getValue('id_endereco')}</p>`;
        html += `<p><strong>Telefone:</strong> ${getValue('id_telefone')}</p>`;
        if (getValue('id_telefone_emergencia')) {
            html += `<p><strong>Telefone de Emergência:</strong> ${getValue('id_telefone_emergencia')}</p>`;
        }
        
        // Bloco Questionário
        html += '<hr><h4>Questionário de Saúde</h4>';

        // Checkboxes únicos (sim/não)
        if (document.getElementById('id_desmaios_ou_vertigens').checked) {
            html += `<p><strong>Desmaio ou Vertigens:</strong> Sim</p>`;
        } else {
            html += `<p><strong>Desmaio ou Vertigens:</strong> Não</p>`;
        }
        
        const doencas = getCheckedLabels('doencas');
        html += `<p><strong>Doenças:</strong> ${doencas.length > 0 ? doencas.join(', ') : 'Nenhuma'}</p>`;
        // Verifica se o checkbox "Outras" de Doenças está marcado
        const doencasCheckboxes = document.querySelectorAll('input[name="doencas"]');
        const outraDoencaChecked = Array.from(doencasCheckboxes).some(c => {
            if (!c.checked) return false;
            const labelText = c.nextElementSibling.textContent.trim().toLowerCase();
            return labelText === 'outro' || labelText === 'outra' || labelText === 'outros' || labelText === 'outras';
        });

        // Só mostra o texto de "Outras Doenças" se o checkbox estiver marcado
        const outrasDoencasValor = getValue('id_outras_doencas');
        if (outraDoencaChecked && outrasDoencasValor) {
             html += `<p><strong>Outras Doenças:</strong> ${outrasDoencasValor}</p>`;
        }

        if (document.getElementById('id_historico_cardiaco_familiar').checked) {
            html += `<p><strong>Histórico cardíaco familiar:</strong> Sim</p>`;
        } else {
            html += `<p><strong>Histórico cardíaco familiar:</strong> Não</p>`;
        }
        
        if (document.getElementById('id_pratica_exercicio').checked) {
            html += `<p><strong>Pratica exercícios:</strong> Sim</p>`;
            html += `<p><strong>Tipo:</strong> ${getValue('id_tipo_exercicio')}</p>`;
            html += `<p><strong>Frequência:</strong> ${getSelectedText('id_frequencia_exercicio')}</p>`;
        } else {
            html += `<p><strong>Pratica exercícios:</strong> Não</p>`;
        }

        const objetivos = getCheckedLabels('objetivos');
        html += `<p><strong>Objetivos:</strong> ${objetivos.length > 0 ? objetivos.join(', ') : 'Nenhum'}</p>`;
        // Verifica se o checkbox "Outros" de Objetivos está marcado
        const objetivosCheckboxes = document.querySelectorAll('input[name="objetivos"]');
        const outroObjetivoChecked = Array.from(objetivosCheckboxes).some(c => {
            if (!c.checked) return false;
            const labelText = c.nextElementSibling.textContent.trim().toLowerCase();
            return labelText === 'outro' || labelText === 'outra' || labelText === 'outros';
        });

        // Só mostra o texto de "Outros" se o checkbox estiver marcado
        const outrosObjetivosValor = getValue('id_outros_objetivos');
        if (outroObjetivoChecked && outrosObjetivosValor) {
             html += `<p><strong>Outros Objetivos:</strong> ${outrosObjetivosValor}</p>`;
        }

        if (document.getElementById('id_declaracao_condicao_especial').checked) {
            html += `<p><strong>Condição especial:</strong> Sim</p>`;
        } else {
            html += `<p><strong>Condição especial:</strong> Não</p>`;
        }

        // Bloco Modalidades
        html += '<hr><h4>Dados da Matrícula(s)</h4>';
        const displayTurmas = document.getElementById('turmas-selecionadas-display').textContent;
        html += `<p><strong>Turmas:</strong> ${displayTurmas}</p>`;

        // Insere o HTML gerado no corpo do modal
        modalBodyConfirmacao.innerHTML = html;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault(); // Impede o envio do formulário

        const customLogicValid = validarLogicaExercicio();
        const gruposCheckboxValid = validarGruposCheckbox();
        const outrosValid = validarLogicaOutros();
        const obrigatoriosValid = validarCamposObrigatorios();
        const turmasValid = validarSelecaoTurmas();

        if (!customLogicValid || !gruposCheckboxValid || !outrosValid || !obrigatoriosValid || !turmasValid) {
            // Se qualquer validação falhar:
            console.log("Validação falhou (JS), mostrando erros.");
            mostrarAbaComErro();
            return;
        }

        console.log("Validação OK, mostrando modal.");
        populateConfirmationModal();
        confirmacaoModal.show();
    });

    btnConfirmar.addEventListener('click', () => {
        confirmacaoModal.hide();

        // Agora sim, envia o formulário para o Django
        console.log("Formulário enviado para o servidor.");
        form.submit();
    });
});