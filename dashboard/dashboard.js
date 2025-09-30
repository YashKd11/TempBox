// Secure Dashboard JS
document.addEventListener("DOMContentLoaded", () => {
  // ---------------- DARK MODE ----------------
  const darkToggle = document.getElementById("darkModeToggle");
  if (localStorage.getItem("darkMode") === "true") {
    document.body.classList.add("dark");
  }
  darkToggle?.addEventListener("click", () => {
    document.body.classList.toggle("dark");
    localStorage.setItem("darkMode", document.body.classList.contains("dark"));
  });

  // ---------------- SECTION SWITCHING ----------------
  const sections = {
    templates: document.getElementById("templatesSection"),
    converter: document.getElementById("converterSection"),
    files: document.getElementById("filesSection"),
    profile: document.getElementById("profileSection"),
    settings: document.getElementById("settingsSection"),
  };
  document.querySelectorAll(".nav-link").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.section;
      document.getElementById("sectionTitle").textContent =
        target.charAt(0).toUpperCase() + target.slice(1);
      Object.keys(sections).forEach((key) => {
        sections[key].classList.toggle("hidden", key !== target);
      });
    });
  });

  // ---------------- PROFILE ----------------
  const userTime = document.getElementById("userTime");
  setInterval(() => {
    const now = new Date();
    userTime.textContent = now.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }, 1000);

  fetch("https://ipapi.co/json/")
    .then((res) => res.json())
    .then((data) => {
      document.getElementById("userIP").textContent = data.ip;
      document.getElementById(
        "userLocation"
      ).textContent = `${data.city}, ${data.country_name}`;

      // Only set username if it's empty (first load), not if user has updated it
      const userNameEl = document.getElementById("userName");
      if (
        !userNameEl.textContent ||
        userNameEl.textContent === "Anonymous User"
      ) {
        userNameEl.textContent = data.org || "Anonymous User";
      }

      const userEmailEl = document.getElementById("userEmail");
      if (
        !userEmailEl.textContent ||
        userEmailEl.textContent === "guest@domain.com"
      ) {
        userEmailEl.textContent = data.ip
          ? `user@${data.country.toLowerCase()}.net`
          : "guest@domain.com";
      }
    })
    .catch(() => {
      document.getElementById("userIP").textContent = "Unavailable";
      document.getElementById("userLocation").textContent = "Unavailable";
    });

  document.getElementById("editProfileBtn").addEventListener("click", () => {
    const newBio = prompt("Update your bio:");
    if (newBio) document.getElementById("userBio").textContent = newBio;
  });

  document.getElementById("logoutBtn").addEventListener("click", () => {
    fetch("/api/logout", { method: "POST", credentials: "include" }).finally(
      () => {
        alert("✅ You have been logged out.");
        window.location.href = "login.html";
      }
    );
  });

  // ---------------- FILE CONVERTER ----------------
  const fileInput = document.getElementById("fileInput");
  const filePreview = document.getElementById("filePreview");
  const convertBtn = document.getElementById("convertBtn");
  const targetFormat = document.getElementById("targetFormat");
  const progressWrap = document.getElementById("convertProgress");
  const progressBar = document.getElementById("convertProgressBar");
  const statusText = document.getElementById("convertStatus");
  const resultBox = document.getElementById("convertResult");

  fileInput?.addEventListener("change", () => {
    resultBox.innerHTML = "";
    if (!fileInput.files.length) {
      filePreview.textContent = "";
      return;
    }
    const file = fileInput.files[0];
    filePreview.innerHTML = `
      <div class="flex items-center justify-between bg-gray-100 dark:bg-gray-700 px-4 py-2 rounded-lg shadow w-full">
        <span class="truncate">${file.name}</span>
        <span class="text-xs text-gray-500">(${(file.size / 1024).toFixed(
          1
        )} KB)</span>
      </div>
    `;
  });

  const showProgress = (pct, text) => {
    progressWrap.classList.remove("hidden");
    progressBar.style.width = `${pct}%`;
    statusText.textContent = text || `${pct}%`;
  };
  const resetProgress = () => {
    progressBar.style.width = `0%`;
    progressWrap.classList.add("hidden");
    statusText.textContent = "";
  };
  const disableUI = (state = true) => {
    convertBtn.disabled = state;
    convertBtn.classList.toggle("opacity-60", state);
  };

  convertBtn?.addEventListener("click", async () => {
    resultBox.innerHTML = "";
    if (!fileInput.files.length) {
      resultBox.innerHTML = `<div class="text-red-500">Please select a file first.</div>`;
      return;
    }

    const file = fileInput.files[0];
    const target = targetFormat.value;
    let chosenTarget = target;
    if (target === "same") {
      if (file.type.startsWith("image/"))
        chosenTarget = file.type.includes("png") ? "png" : "jpg";
      else chosenTarget = "server";
    }

    disableUI(true);
    showProgress(5, "Preparing...");

    try {
      if (
        file.type.startsWith("image/") &&
        (chosenTarget === "png" || chosenTarget === "jpg")
      ) {
        await convertImageClientSide(file, chosenTarget);
      } else {
        await uploadToServer(file, chosenTarget);
      }
    } catch (err) {
      resultBox.innerHTML = `<div class="text-red-500">Error: ${
        err.message || err
      }</div>`;
    } finally {
      disableUI(false);
    }
  });

  function convertImageClientSide(file, targetExt) {
    return new Promise(async (resolve, reject) => {
      showProgress(10, "Reading file...");
      const dataUrl = await readFileAsDataURL(file);
      const img = await loadImage(dataUrl);
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      canvas.getContext("2d").drawImage(img, 0, 0);
      showProgress(60, "Converting...");
      canvas.toBlob(
        (blob) => {
          const downloadUrl = URL.createObjectURL(blob);
          const nameBase = file.name.replace(/\.[^/.]+$/, "");
          resultBox.innerHTML = `
            <a href="${downloadUrl}" download="${nameBase}.${targetExt}"
              class="inline-block px-4 py-2 bg-green-500 text-white rounded">Download</a>`;
          showProgress(100, "Done");
          resolve();
        },
        targetExt === "png" ? "image/png" : "image/jpeg",
        0.92
      );
    });
  }
  function readFileAsDataURL(file) {
    return new Promise((res, rej) => {
      const fr = new FileReader();
      fr.onload = () => res(fr.result);
      fr.onerror = rej;
      fr.readAsDataURL(file);
    });
  }
  function loadImage(dataUrl) {
    return new Promise((res, rej) => {
      const img = new Image();
      img.onload = () => res(img);
      img.onerror = rej;
      img.src = dataUrl;
    });
  }

  function uploadToServer(file, target) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/convert");
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 70);
          showProgress(pct, `Uploading... ${pct}%`);
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const blob = new Blob([xhr.response], {
            type: xhr.getResponseHeader("Content-Type"),
          });
          const url = URL.createObjectURL(blob);
          resultBox.innerHTML = `<a href="${url}" download="converted-file" class="inline-block px-4 py-2 bg-green-500 text-white rounded">Download</a>`;
          showProgress(100, "Converted");
          resolve();
        } else {
          reject(new Error(`Server returned ${xhr.status}`));
        }
      };
      xhr.onerror = () => reject(new Error("Network error"));
      const fd = new FormData();
      fd.append("file", file);
      fd.append("target", target);
      xhr.responseType = "arraybuffer";
      xhr.send(fd);
    });
  }

  // ---------------- TEMPLATES ----------------
  document.querySelectorAll("#templatesSection button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const templateName = btn.closest("div").querySelector("h3").textContent;
      alert(`📄 You selected: ${templateName}`);
    });
  });
});
