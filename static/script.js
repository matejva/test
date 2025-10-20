// Spustenie až po načítaní DOM
document.addEventListener("DOMContentLoaded", () => {
  console.log("Frontend HRC & Navate načítaný ✅");

  // Ak je Bootstrap modal k dispozícii
  const editModalEl = document.getElementById('editModal');
  let editModal;
  if (editModalEl) {
    editModal = new bootstrap.Modal(editModalEl);
  }

  // Funkcia pre otvorenie modálu na editáciu záznamu
  window.openEditModal = function(id, projectId, amount, note) {
    const form = document.getElementById('editForm');
    if (!form) return;

    // Naplnenie formulára údajmi
    form.action = '/entry/update';
    form.querySelector('input[name="id"]').value = id;
    form.querySelector('select[name="project_id"]').value = projectId;
    form.querySelector('input[name="amount"]').value = amount;
    form.querySelector('input[name="note"]').value = note;

    // Zobrazenie modálu
    if (editModal) editModal.show();
  };

  // Ak máš graf na dashboarde, inicializuj Chart.js
  const hoursChartEl = document.getElementById('hoursChart');
  if (hoursChartEl) {
    const ctx = hoursChartEl.getContext('2d');
    const labels = hoursChartEl.dataset.labels ? JSON.parse(hoursChartEl.dataset.labels) : [];
    const data = hoursChartEl.dataset.values ? JSON.parse(hoursChartEl.dataset.values) : [];
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Hodiny',
          data: data,
          backgroundColor: 'rgba(0,191,166,0.7)',
          borderRadius: 6
        }]
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      }
    });
  }
});
