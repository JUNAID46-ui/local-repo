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

// Auto-dismiss flash alerts after 5 seconds
document.querySelectorAll('.alert').forEach(function(alert) {
    setTimeout(function() {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-10px)';
        setTimeout(function() { alert.remove(); }, 300);
    }, 5000);
});

// Pipeline status polling (dashboard only)
(function() {
    var tracker = document.getElementById('pipelineTracker');
    if (!tracker) return;

    var statusBadge = document.getElementById('pipelineStatusBadge');
    var pipelineMode = document.getElementById('pipelineMode');
    var pipelineBusiness = document.getElementById('pipelineBusiness');
    var pipelineTopic = document.getElementById('pipelineTopic');
    var pipelineStarted = document.getElementById('pipelineStarted');
    var pipelineErrors = document.getElementById('pipelineErrors');
    var stages = tracker.querySelectorAll('.pipeline-stage');

    function updateStatus() {
        fetch('/api/status')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.running) {
                    tracker.style.display = '';
                    if (statusBadge) {
                        statusBadge.className = 'badge badge-success';
                        statusBadge.innerHTML = '<span class="status-dot running"></span> Pipeline Running';
                    }
                    if (pipelineMode) pipelineMode.textContent = data.mode || '';
                    if (pipelineBusiness) pipelineBusiness.textContent = 'Business: ' + (data.current_business || 'Initializing...');
                    if (pipelineTopic) pipelineTopic.textContent = data.current_topic ? 'Topic: ' + data.current_topic : '';
                    if (pipelineStarted) pipelineStarted.textContent = 'Started: ' + (data.started_at || '');

                    stages.forEach(function(stage, i) {
                        stage.classList.remove('completed', 'active');
                        if (i < data.stage_index) {
                            stage.classList.add('completed');
                        } else if (i === data.stage_index) {
                            stage.classList.add('active');
                        }
                    });

                    if (data.errors && data.errors.length > 0) {
                        pipelineErrors.style.display = '';
                        pipelineErrors.innerHTML = data.errors.map(function(e) {
                            return '<div class="pipeline-error">' + escapeHtml(e) + '</div>';
                        }).join('');
                    } else {
                        pipelineErrors.style.display = 'none';
                    }
                } else {
                    if (tracker.style.display !== 'none' && data.current_stage === 'Complete') {
                        stages.forEach(function(stage) { stage.classList.add('completed'); });
                        setTimeout(function() { tracker.style.display = 'none'; }, 3000);
                    } else if (!tracker.dataset.wasRunning) {
                        tracker.style.display = 'none';
                    }
                    if (statusBadge) {
                        statusBadge.className = 'badge badge-gray';
                        statusBadge.innerHTML = '<span class="status-dot idle"></span> Idle';
                    }
                }
                tracker.dataset.wasRunning = data.running ? '1' : '';
            })
            .catch(function() {});
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    setInterval(updateStatus, 3000);
    updateStatus();
})();
