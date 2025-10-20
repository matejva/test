function openEditModal(id, projectId, amount, note) {
  const modal = document.getElementById('editModal');
  modal.style.display = 'block';
  const form = document.getElementById('editForm');
  form.action = '/edit_record/' + id;  // iba ak route existuje
  form.project_id.value = projectId;
  form.amount.value = amount;
  form.note.value = note;
}
window.onclick = function(event) {
  const modal = document.getElementById('editModal');
  if (event.target === modal) modal.style.display = 'none';
}
