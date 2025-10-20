document.addEventListener("DOMContentLoaded", function () {
  const editModal = document.getElementById("editModal");
  if (editModal) {
    editModal.addEventListener("show.bs.modal", function (event) {
      const button = event.relatedTarget;
      const id = button.getAttribute("data-id");
      fetch(`/entry/${id}/json`)
        .then(r => r.json())
        .then(data => {
          document.getElementById("edit-id").value = data.id;
          document.getElementById("edit-date").value = data.date;
          document.getElementById("edit-project").value = data.project_id;
          document.getElementById("edit-amount").value = data.amount;
          document.getElementById("edit-note").value = data.note;
        });
    });
  }
});
