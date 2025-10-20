document.addEventListener("DOMContentLoaded", () => {
  console.log("Frontend HRC & Navate načítaný ✅");

  // ======== Modal na editáciu ========
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
    form.querySelector('input[name="id"]').value = id;
    form.querySelector('select[name="project_id"]').value = projectId;
    form.querySelector('input[name="amount"]').value = amount;
    form.querySelector('textarea[name="note"]').value = note;

    // Zobrazenie modálu
    if (editModal) editModal.show();
  };

  // ======== (Voliteľné) Chart.js ========
  const hoursChartEl = document.getElementById('hoursChart');
  if (hoursChartEl) {
    const ctx = hoursChartEl.getContext('2d');
    const labels = JSON.parse(hoursChartEl.dataset.labels || "[]");
    const data = JSON.parse(hoursChartEl.dataset.values || "[]");
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
