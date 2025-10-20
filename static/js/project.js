document.addEventListener("DOMContentLoaded", function () {
  const editModal = document.getElementById("editProjectModal");
  if (editModal) {
    editModal.addEventListener("show.bs.modal", function (event) {
      const button = event.relatedTarget;
      const id = button.getAttribute("data-id");
      fetch(`/project/${id}/json`)
        .then(r => r.json())
        .then(data => {
          document.getElementById("edit-project-id").value = data.id;
          document.getElementById("edit-project-name").value = data.name;
          document.getElementById("edit-project-unit").value = data.unit_type;
          document.getElementById("edit-project-description").value = data.description || "";
        });
    });
  }
});
