function openModal() {
    document.getElementById('pipelineModal').classList.add('active');
}

function closeModal() {
    document.getElementById('pipelineModal').classList.remove('active');
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeModal();
});

document.getElementById('pipelineModal').addEventListener('click', function(e) {
    if (e.target === this) closeModal();
});
