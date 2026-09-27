/**
 * Intelligent Document Extraction Platform - Frontend Application Script
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. Setup Dropzone and File Input
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("fileInput");
    const selectedFileName = document.getElementById("selectedFileName");
    const uploadForm = document.getElementById("uploadForm");
    const uploadBtn = document.getElementById("uploadBtn");
    const uploadBtnText = document.getElementById("uploadBtnText");
    const uploadSpinner = document.getElementById("uploadSpinner");
    const errorAlert = document.getElementById("errorAlert");
    const errorMessage = document.getElementById("errorMessage");

    if (dropzone && fileInput) {
        dropzone.addEventListener("click", () => fileInput.click());

        ["dragenter", "dragover"].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropzone.classList.add("dragover");
            }, false);
        });

        ["dragleave", "drop"].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropzone.classList.remove("dragover");
            }, false);
        });

        dropzone.addEventListener("drop", (e) => {
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                updateFileNameDisplay();
            }
        });

        fileInput.addEventListener("change", updateFileNameDisplay);
    }

    function updateFileNameDisplay() {
        if (fileInput && fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
            selectedFileName.textContent = `Selected: ${file.name} (${sizeMb} MB)`;
            selectedFileName.style.color = "#2563eb";
        }
    }

    // 2. Upload Form Submission via Fetch API
    if (uploadForm) {
        uploadForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            if (errorAlert) errorAlert.style.display = "none";

            const file = fileInput.files[0];
            const docType = document.getElementById("documentType").value;

            if (!file) {
                showError("Please select a document file to upload.");
                return;
            }

            const formData = new FormData();
            formData.append("file", file);
            formData.append("document_type", docType);

            // UI Loading state
            if (uploadBtn) uploadBtn.disabled = true;
            if (uploadSpinner) uploadSpinner.style.display = "inline-block";
            if (uploadBtnText) uploadBtnText.textContent = "Processing Document...";

            try {
                const response = await fetch("/api/v1/documents/process", {
                    method: "POST",
                    body: formData
                });

                const data = await response.json();

                if (!response.ok) {
                    const err = data.error || {};
                    const msg = err.message || "Failed to process document.";
                    const code = err.code ? `[${err.code}] ` : "";
                    showError(`${code}${msg}`);
                } else {
                    // Fetch document ID from DB or refresh page
                    window.location.reload();
                }
            } catch (err) {
                showError(`Network or server connection error: ${err.message}`);
            } finally {
                if (uploadBtn) uploadBtn.disabled = false;
                if (uploadSpinner) uploadSpinner.style.display = "none";
                if (uploadBtnText) uploadBtnText.textContent = "Upload & Process";
            }
        });
    }

    function showError(msg) {
        if (errorAlert && errorMessage) {
            errorMessage.textContent = msg;
            errorAlert.style.display = "flex";
            errorAlert.scrollIntoView({ behavior: "smooth" });
        } else {
            alert(msg);
        }
    }

    // 3. Search and Filter in Dashboard Table
    const searchInput = document.getElementById("searchDocuments");
    const typeFilter = document.getElementById("filterType");
    const tableBody = document.getElementById("documentsTableBody");

    if (searchInput && tableBody) {
        const filterRows = () => {
            const query = searchInput.value.toLowerCase();
            const selectedType = typeFilter ? typeFilter.value.toLowerCase() : "";
            const rows = tableBody.getElementsByTagName("tr");

            for (let row of rows) {
                const nameCell = row.querySelector(".doc-name");
                const typeCell = row.querySelector(".doc-type");

                if (!nameCell) continue;

                const nameText = nameCell.textContent.toLowerCase();
                const typeText = typeCell ? typeCell.textContent.toLowerCase() : "";

                const matchesQuery = nameText.includes(query);
                const matchesType = !selectedType || typeText.includes(selectedType);

                row.style.display = (matchesQuery && matchesType) ? "" : "none";
            }
        };

        searchInput.addEventListener("input", filterRows);
        if (typeFilter) typeFilter.addEventListener("change", filterRows);
    }
});

/**
 * Copies the raw JSON content to the system clipboard.
 */
function copyJsonToClipboard() {
    const jsonElem = document.getElementById("rawJsonContent");
    if (!jsonElem) return;
    navigator.clipboard.writeText(jsonElem.innerText)
        .then(() => {
            const copyBtn = document.getElementById("copyJsonBtn");
            if (copyBtn) {
                const orig = copyBtn.innerHTML;
                copyBtn.innerHTML = "Copied to Clipboard!";
                setTimeout(() => copyBtn.innerHTML = orig, 2000);
            }
        })
        .catch(err => alert("Could not copy JSON: " + err));
}
