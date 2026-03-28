/* Eval UI — Core JavaScript */

(function () {
    "use strict";

    // ── Table Sorting ──

    document.querySelectorAll("table[data-sortable]").forEach(function (table) {
        var headers = table.querySelectorAll("thead th[data-sort]");
        headers.forEach(function (th, colIndex) {
            th.addEventListener("click", function () {
                var dir = th.classList.contains("sort-asc") ? "desc" : "asc";
                headers.forEach(function (h) {
                    h.classList.remove("sort-asc", "sort-desc");
                });
                th.classList.add("sort-" + dir);
                sortTable(table, colIndex, dir, th.dataset.sort);
            });
        });
    });

    function sortTable(table, colIndex, direction, dataType) {
        var tbody = table.querySelector("tbody");
        if (!tbody) return;
        var rows = Array.from(tbody.querySelectorAll("tr"));

        rows.sort(function (a, b) {
            var aVal = getCellValue(a, colIndex, dataType);
            var bVal = getCellValue(b, colIndex, dataType);
            if (aVal < bVal) return direction === "asc" ? -1 : 1;
            if (aVal > bVal) return direction === "asc" ? 1 : -1;
            return 0;
        });

        rows.forEach(function (row) {
            tbody.appendChild(row);
        });
    }

    function getCellValue(row, index, dataType) {
        var cell = row.cells[index];
        if (!cell) return "";
        var text = cell.textContent.trim();
        if (dataType === "number") return parseFloat(text) || 0;
        if (dataType === "date") return new Date(text).getTime() || 0;
        return text.toLowerCase();
    }

    // ── Auto-refresh (for live pages) ──

    var refreshEl = document.querySelector("[data-auto-refresh]");
    if (refreshEl) {
        var interval = parseInt(refreshEl.dataset.autoRefresh, 10) || 5000;
        setInterval(function () {
            // Reload the page if the run is still active
            var statusEl = document.querySelector("[data-run-status]");
            if (statusEl) {
                var status = statusEl.dataset.runStatus;
                if (status === "queued" || status === "running" || status === "scoring" || status === "provisioning") {
                    window.location.reload();
                }
            }
        }, interval);
    }

    // ── Tabs ──

    document.querySelectorAll(".tabs .tab").forEach(function (tab) {
        tab.addEventListener("click", function () {
            var group = tab.closest(".tabs");
            var container = group.parentElement;
            var targetId = tab.dataset.tab;

            group.querySelectorAll(".tab").forEach(function (t) {
                t.classList.remove("active");
            });
            tab.classList.add("active");

            container.querySelectorAll(".tab-content").forEach(function (c) {
                c.classList.remove("active");
            });
            var target = container.querySelector("#" + targetId);
            if (target) target.classList.add("active");
        });
    });

    // ── Multi-select for comparisons ──

    var compareBtn = document.getElementById("compare-selected");
    if (compareBtn) {
        var checkboxes = document.querySelectorAll("input[name='compare-run']");

        function updateCompareButton() {
            var checked = document.querySelectorAll("input[name='compare-run']:checked");
            compareBtn.disabled = checked.length < 2;
            compareBtn.textContent = "Compare Selected (" + checked.length + ")";
        }

        checkboxes.forEach(function (cb) {
            cb.addEventListener("change", updateCompareButton);
        });

        compareBtn.addEventListener("click", function () {
            var ids = [];
            document.querySelectorAll("input[name='compare-run']:checked").forEach(function (cb) {
                ids.push(cb.value);
            });
            if (ids.length >= 2) {
                window.location.href = "/eval/comparisons?runs=" + ids.join(",");
            }
        });

        updateCompareButton();
    }

    // ── Filter form submission ──

    document.querySelectorAll(".filter-bar form").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            // Remove empty fields from query string
            var inputs = form.querySelectorAll("input, select");
            inputs.forEach(function (input) {
                if (!input.value) input.disabled = true;
            });
        });
    });

    // ── Progress bar animation ──

    document.querySelectorAll(".progress-bar[data-width]").forEach(function (bar) {
        setTimeout(function () {
            bar.style.width = bar.dataset.width + "%";
        }, 100);
    });

})();
