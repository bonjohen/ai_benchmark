/* Publication UI interactions */

function toggleDetail(headerEl) {
    var entry = headerEl.closest('.pub-entry');
    var detail = entry.querySelector('.entry-detail');
    if (detail) {
        detail.style.display = detail.style.display === 'none' ? 'block' : 'none';
    }
}
