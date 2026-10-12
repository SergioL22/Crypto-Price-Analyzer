"use strict";
(() => {
 const exportButton = $("holdings-export"), backupStatus = $("backup-status");
 exportButton.addEventListener("click", async () => {
  if (portfolioMutationPending) return;
  portfolioMutationPending = true; exportButton.disabled = true; backupStatus.textContent = "Preparing saved portfolio backup…";
  let url = null;
  try {
   const response = await fetch("/v1/holdings/export");
   if (!response.ok) throw new Error("Export failed");
   const content = await response.text();
   const parsed = JSON.parse(content);
   if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Invalid backup");
   url = URL.createObjectURL(new Blob([content], {type:"application/json"}));
   const link = el("a"); link.href = url; link.download = "portfolio-backup.json";
   document.body.append(link); link.click(); link.remove();
   backupStatus.textContent = "Backup download requested. Check your browser downloads for portfolio-backup.json. Saved holdings were not changed.";
  } catch {
   backupStatus.textContent = "Could not download a backup. Check the saved portfolio file and try again. Saved holdings were not changed.";
  } finally {
   if (url !== null) { const downloadUrl = url; setTimeout(() => URL.revokeObjectURL(downloadUrl), 60000); }
   portfolioMutationPending = false; exportButton.disabled = false;
  }
 });
})();
