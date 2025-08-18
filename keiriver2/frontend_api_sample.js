// frontend_api_sample.js
// React/Vue等でAPI呼び出しする例
async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch('/upload', {
    method: 'POST',
    body: formData
  });
  return await res.json();
}
