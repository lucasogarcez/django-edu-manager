document.addEventListener("DOMContentLoaded", function () {

    const tomSelectMultiOptions = {
        plugins: ['remove_button'],
        placeholder: "Selecione um ou mais...",
        persist: false,
        create: false
    };

    // IDs dos campos que serão transformados
    const campos = [
        '#id_professores',
        '#id_estagiarios',
        '#id_dias__dia_semana'
    ];

    campos.forEach(selector => {
        const el = document.querySelector(selector);
        if (!el) return;

        // Remove placeholder nativo (caso Crispy/Django tenha injetado)
        el.removeAttribute('placeholder');

        // Inicializa o Tom Select (registrando em TomSelect.instances)
        const select = new TomSelect(selector, tomSelectMultiOptions);

        if (select.items.length > 0) {
            select.control.classList.add('has-items');
        }

        select.on('change', () => {
            if (select.items.length > 0) {
                select.control.classList.add('has-items');
            } else {
                select.control.classList.remove('has-items');
            }
        });
    });

});
