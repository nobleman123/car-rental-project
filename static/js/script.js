document.addEventListener("DOMContentLoaded", function() {
    // Gelecekteki tarihleri engelleme gibi basit kontroller buraya eklenebilir
    const dateInputs = document.querySelectorAll('input[type="date"]');
    const today = new Date().toISOString().split('T')[0];
    
    dateInputs.forEach(input => {
        input.setAttribute('min', today);
    });
});