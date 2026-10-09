(function () {
  const csrf = document.querySelector('meta[name="csrf"]').content;
  const box = document.getElementById("scanner");
  const url = box.dataset.url;
  const video = document.getElementById("video");
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const statusEl = document.getElementById("scan-status");
  const resultEl = document.getElementById("result");
  const startBtn = document.getElementById("start");
  const fileInput = document.getElementById("file");
  let scanning = false, busy = false;

  function show(ok, msg) {
    resultEl.className = "result " + (ok ? "ok" : "bad");
    resultEl.textContent = msg;
  }

  async function submit(payload) {
    if (busy) return;
    busy = true;
    try {
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ payload: payload }),
      });
      const d = await r.json();
      show(d.ok, d.message);
    } catch (e) {
      show(false, "Network error. Please try again.");
    }
    setTimeout(function () { busy = false; }, 3000);
  }

  function decode(imageData) {
    return jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: "attemptBoth" });
  }

  function tick() {
    if (!scanning) return;
    if (video.readyState === video.HAVE_ENOUGH_DATA && !busy) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0);
      const code = decode(ctx.getImageData(0, 0, canvas.width, canvas.height));
      if (code && code.data) submit(code.data);
    }
    requestAnimationFrame(tick);
  }

  startBtn.addEventListener("click", async function () {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      show(false, "Camera needs https or localhost. You can scan an image file instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      video.srcObject = stream;
      await video.play();
      video.hidden = false;
      startBtn.hidden = true;
      scanning = true;
      statusEl.textContent = "Scanning. Hold the QR code steady.";
      tick();
    } catch (e) {
      show(false, "Camera access was blocked. Allow it in the browser, or scan an image file.");
    }
  });

  fileInput.addEventListener("change", function () {
    const f = fileInput.files[0];
    if (!f) return;
    const img = new Image();
    img.onload = function () {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      const code = decode(ctx.getImageData(0, 0, canvas.width, canvas.height));
      if (code && code.data) submit(code.data);
      else show(false, "No QR code found in that image.");
      URL.revokeObjectURL(img.src);
    };
    img.onerror = function () { show(false, "Could not read that image."); };
    img.src = URL.createObjectURL(f);
    fileInput.value = "";
  });
})();
