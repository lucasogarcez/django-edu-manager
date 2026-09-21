document.addEventListener("DOMContentLoaded", function() {
        // 1. Inicializa as portas de Seleção Múltipla (Tags dinâmicas)
        document.querySelectorAll('.tomselect-multiple').forEach((el) => {
            new TomSelect(el, {
                plugins: ['remove_button'], // Adiciona o botão 'X' para remover a tag
                create: false,
                allowEmptyOption: true,
                placeholder: "Selecione uma ou várias opções...",
                render: {
                    no_results: function(data, escape) {
                        return '<div class="no-results">Nenhum sinal encontrado na rede</div>';
                    }
                }
            });
        });

        // 2. Inicializa as portas de Seleção Simples (Com busca inteligente)
        document.querySelectorAll('.tomselect-single').forEach((el) => {
            new TomSelect(el, {
                create: false,
                allowEmptyOption: false,
                placeholder: "Selecione uma opção..."
            });
        });
    });