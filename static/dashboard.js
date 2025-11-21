// Secure Dashboard JS
document.addEventListener("DOMContentLoaded", () => {
  // ---------------- DARK MODE ----------------
  const btn = document.getElementById("darkModeToggle");
  const root = document.documentElement;

  // Load initial theme from localStorage
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme === "dark") {
    root.classList.add("dark");
  }

  // Set initial button text
  updateButtonText();

  btn.addEventListener("click", () => {
    const isDark = root.classList.toggle("dark");
    localStorage.setItem("theme", isDark ? "dark" : "light");
    updateButtonText();
  });

  function updateButtonText() {
    const isDark = root.classList.contains("dark");
    btn.textContent = isDark ? " Dark Mode" : " Light Mode";

    // Sync the settings toggle checkbox
    const settingsToggle = document.getElementById("darkModeSwitch");
    if (settingsToggle) {
      settingsToggle.checked = isDark;
    }
  }

  // ---------------- SECTION SWITCHING ----------------
  const sections = {
    templates: document.getElementById("templatesSection"),
    converter: document.getElementById("converterSection"),
    files: document.getElementById("filesSection"),
    profile: document.getElementById("profileSection"),
    settings: document.getElementById("settingsSection"),
    activity: document.getElementById("activitySection"),
  };

  // Hide all sections except the default one (activity) on load
  Object.keys(sections).forEach((key) =>
    sections[key].classList.toggle("hidden", key !== "activity")
  );

  document.querySelectorAll(".nav-link").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.section;
      document.getElementById("sectionTitle").textContent =
        target === "activity"
          ? "Activity Log"
          : target.charAt(0).toUpperCase() + target.slice(1);
      Object.keys(sections).forEach((key) => {
        sections[key].classList.toggle("hidden", key !== target);
      });

      // If the activity log is the target, load its content
      if (target === "activity") {
        loadActivityLog();
      } else if (target === "templates") {
        loadStats();
      } else if (target === "files") {
        loadUserFiles();
      }
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

  // Fetch IP and location on dashboard load, and update backend
  Promise.race([
    fetch("https://ipapi.co/json/"),
    new Promise((_, reject) => setTimeout(() => reject(new Error('Request timed out')), 5000))
  ])
    .then((res) => res.json())
    .then((data) => {
      document.getElementById("userIP").textContent = data.ip || "Unavailable";
      document.getElementById("userLocation").textContent = `${
        data.city || "Unavailable"
      }, ${data.country_name || "Unavailable"}`;

      // Send IP/location data to backend to update user profile
      fetch("/api/profile", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ip: data.ip,
          city: data.city,
          country_name: data.country_name,
          org: data.org,
        }),
      }).catch((err) => console.error("Failed to update IP/location:", err));
    })
    .catch(() => {
      document.getElementById("userIP").textContent = "Unavailable";
      document.getElementById("userLocation").textContent = "Unavailable";
    });

  const profileForm = document.getElementById("profileForm");
  const toggleEditProfileFormBtn = document.getElementById(
    "toggleEditProfileFormBtn"
  );
  const cancelEditProfileBtn = document.getElementById("cancelEditProfileBtn");
  const profileDisplayElements = {
    userName: document.getElementById("userName"),
    userEmail: document.getElementById("userEmail"),
    userBio: document.getElementById("userBio"),
    sidebarName: document.getElementById("sidebarName"),
    userPhone: document.getElementById("userPhone"),
    userLocation: document.getElementById("userLocation"),
  };

  // Toggle profile edit form visibility
  toggleEditProfileFormBtn?.addEventListener("click", () => {
    profileForm?.classList.toggle("hidden");
    toggleEditProfileFormBtn.classList.toggle("hidden"); // Hide edit button when form is open
  });

  cancelEditProfileBtn?.addEventListener("click", () => {
    profileForm?.classList.add("hidden");
    toggleEditProfileFormBtn.classList.remove("hidden"); // Show edit button when form is closed
  });

  document.getElementById("logoutBtn").addEventListener("click", () => {
    fetch("/api/logout", { method: "POST", credentials: "include" })
      .then((res) => res.json())
      .then((data) => {
        alert(`✅ ${data.message}`);
        window.location.href = "/login"; // Redirect to login page
      })
      .catch((err) => {
        console.error("Logout error:", err);
        alert("An error occurred during logout.");
      });
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

  const conversionMap = {
    jpg: ["png", "pdf"],
    jpeg: ["png", "pdf"],
    png: ["jpg", "gif", "pdf"],
    pdf: ["docx", "jpg", "txt"],
    docx: ["pdf"],
    csv: ["xlsx", "json"],
    xlsx: ["csv"],
    txt: ["pdf"],
    html: ["pdf"],
    mp4: ["mp3", "mkv"],
    mp3: ["wav"],
    wav: ["mp3"],
    mov: ["mp4"],
    zip: ["rar"],
    rar: ["zip"],
    "7z": ["zip"],
    py: ["exe"],
    ts: ["js"],
    scss: ["css"],
    json: ["csv"],
    md: ["pdf"],
    svg: ["png"],
    heic: ["jpg"],
    xml: ["json"],
    sqlite: ["csv"],
    ipynb: ["py"],
  };

  fileInput?.addEventListener("change", () => {
    resultBox.innerHTML = "";
    targetFormat.innerHTML = ""; // Clear previous options

    if (!fileInput.files.length) {
      filePreview.textContent = "";
      const defaultOption = document.createElement("option");
      defaultOption.textContent = "Select a file first";
      targetFormat.appendChild(defaultOption);
      targetFormat.disabled = true;
      return;
    }

    targetFormat.disabled = false;
    const file = fileInput.files[0];
    const fileName = file.name;
    const fileExtension = fileName.split(".").pop().toLowerCase();

    filePreview.innerHTML = `
      <div class="flex items-center justify-between bg-gray-100 dark:bg-gray-700 px-4 py-2 rounded-lg shadow w-full">
        <span class="truncate">${file.name}</span>
        <span class="text-xs text-gray-500">(${(file.size / 1024).toFixed(
          1
        )} KB)</span>
      </div>
    `;

    const allowedConversions = conversionMap[fileExtension];

    if (allowedConversions) {
      allowedConversions.forEach((format) => {
        const option = document.createElement("option");
        option.value = format;
        option.textContent = format.toUpperCase();
        targetFormat.appendChild(option);
      });
    } else {
      const option = document.createElement("option");
      option.textContent = "No conversions available";
      targetFormat.appendChild(option);
      targetFormat.disabled = true;
    }
  });

  const showProgress = (pct, text) => {
    progressWrap.classList.remove("hidden");
    progressBar.style.width = `${pct}%`;
    statusText.textContent = text || `${pct}%`;
  };
  const resetProgress = () => {
    progressBar.style.width = "0%";
    progressWrap.classList.add("hidden");
    statusText.textContent = "";
  };
  const disableUI = (state = true) => {
    convertBtn.disabled = state;
    convertBtn.classList.toggle("opacity-60", state);
  };

  convertBtn?.addEventListener("click", async () => {
    //async means that this function have to wait for the action to complete
    resultBox.innerHTML = "";
    if (!fileInput.files.length) {
      resultBox.innerHTML = `<div class="text-red-500">Please select a file first.</div>`;
      return;
    }

    const file = fileInput.files[0];
    const target = targetFormat.value; //dropdown ka selection
    let chosenTarget = target;
    if (target === "same") {
      if (file.type.startsWith("image/"))
        chosenTarget = file.type.includes("png") ? "png" : "jpg";
      // Client-side image conversion
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
        await uploadToServer(
          file,
          chosenTarget === "same" ? "server" : chosenTarget
        );
      }
    } catch (err) {
      resultBox.innerHTML = `<div class="text-red-500">Conversion Error: ${
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
      xhr.onload = function() {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const responseData = JSON.parse(xhr.responseText); // Expect JSON response
            if (responseData.download_url) {
              resultBox.innerHTML = `<a href="${responseData.download_url}" download="converted-file" class="inline-block px-4 py-2 bg-green-500 text-white rounded">Download</a>`;
              showProgress(100, "Converted");
              resolve();
            } else {
              reject(new Error("Server response missing download URL."));
            }
          } catch (e) {
            reject(new Error("Failed to parse server response."));
          }
        } else {
          let errorMessage = `Server returned ${xhr.status}`;
          try {
            const errorData = JSON.parse(xhr.responseText);
            errorMessage = errorData.error || errorMessage;
          } catch (e) {
            // responseText might not be JSON
          }
          reject(new Error(errorMessage));
        }
      };
      xhr.onerror = () => reject(new Error("Network error"));
      const fd = new FormData();
      fd.append("file", file);
      fd.append("target", target);
      xhr.send(fd);
    });
  }

  // ---------------- STATS ----------------
  const templatesUsedEl = document.getElementById("templatesUsed");
  const filesConvertedEl = document.getElementById("filesConverted");
  const filesSharedEl = document.getElementById("filesShared");

  async function loadStats() {
    try {
      const response = await fetch("/api/stats");
      if (!response.ok) {
        throw new Error(`Failed to fetch stats: ${response.statusText}`);
      }
      const stats = await response.json();
      templatesUsedEl.textContent = stats.templatesUsed;
      filesConvertedEl.textContent = stats.filesConverted;
      filesSharedEl.textContent = stats.filesShared;
    } catch (error) {
      console.error("Error fetching stats:", error);
      templatesUsedEl.textContent = "Error";
      filesConvertedEl.textContent = "Error";
      filesSharedEl.textContent = "Error";
    }
  }

  // ---------------- MODALS ----------------
  const uploadShareModal = document.getElementById("uploadShareModal");
  const uploadAndShareBtn = document.getElementById("uploadAndShareBtn");
  const cancelUploadShareBtn = document.getElementById("cancelUploadShareBtn");

  uploadAndShareBtn?.addEventListener("click", () => {
    uploadShareModal.classList.remove("hidden");
  });

  cancelUploadShareBtn?.addEventListener("click", () => {
    uploadShareModal.classList.add("hidden");
  });

  // Logic for upload modal's temporary/permanent options
  const uploadExpirationContainer = document.getElementById("uploadExpirationContainer");
  const uploadFileTypePermanent = document.getElementById("uploadFileTypePermanent");
  const uploadFileTypeTemporary = document.getElementById("uploadFileTypeTemporary");

  uploadFileTypePermanent?.addEventListener("change", () => {
    uploadExpirationContainer.classList.add("hidden");
  });

  uploadFileTypeTemporary?.addEventListener("change", () => {
    uploadExpirationContainer.classList.remove("hidden");
  });


  const uploadShareForm = document.getElementById("uploadShareForm");

  uploadShareForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById("fileToUpload");
    const file = fileInput.files[0];

    if (!file) {
      alert("Please select a file.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    // Append file type and expiration data
    const fileType = document.querySelector('input[name="upload_file_type"]:checked').value;
    formData.append("file_type", fileType);

    if (fileType === "temporary") {
      const expirationHours = document.getElementById("uploadExpirationHours").value;
      if (expirationHours) {
        formData.append("expiration_hours", expirationHours);
      }
    }



    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        // Instead of an alert, just close the modal and refresh the list.
        // The user can get the link from the "Share" button on the new file entry.
        uploadShareModal.classList.add("hidden");
        loadUserFiles(); // Refresh the file list

        // Optional: Show a toast/notification for better UX, but for now, this is cleaner.
        // For example, you could implement a small notification banner at the top of the page.
        console.log(`File uploaded. Shareable link: ${data.share_url}`);
      } else {
        alert(`❌ Error uploading file: ${data.error || response.statusText}`);
      }
    } catch (error) {
      console.error("Error uploading file:", error);
      alert("An error occurred while uploading the file.");
    }
  });

  // ---------------- SHARE FILE MODAL ----------------
  const shareFileModal = document.getElementById("shareFileModal");
  const closeShareModalBtn = document.getElementById("closeShareModalBtn");
  const copyShareLinkBtn = document.getElementById("copyShareLinkBtn");
  const shareLinkInput = document.getElementById("shareLinkInput");

  closeShareModalBtn.addEventListener("click", () => {
    shareFileModal.classList.add("hidden");
  });

  copyShareLinkBtn.addEventListener("click", () => {
    shareLinkInput.select();
    document.execCommand("copy");
    // Provide feedback to the user
    const originalIcon = copyShareLinkBtn.innerHTML;
    copyShareLinkBtn.innerHTML = `<i class="fa-solid fa-check text-green-500"></i>`;
    setTimeout(() => {
      copyShareLinkBtn.innerHTML = originalIcon;
    }, 2000);
  });



  // ---------------- SETTINGS ----------------
  // Dark mode toggle in settings
  const darkModeSwitch = document.getElementById("darkModeSwitch");
  if (darkModeSwitch) {
    darkModeSwitch.addEventListener("change", () => {
      const isDark = darkModeSwitch.checked;
      root.classList.toggle("dark", isDark);
      localStorage.setItem("theme", isDark ? "dark" : "light");
      updateButtonText();
    });
  }

  const saveUsernameBtn = document.getElementById("saveUsername");
  saveUsernameBtn?.addEventListener("click", async () => {
    const newUsername = document.getElementById("newUsername").value;
    if (!newUsername) {
      alert("Please enter a new username.");
      return;
    }

    try {
      const response = await fetch("/api/profile", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username: newUsername }),
      });

      const data = await response.json();

      if (response.ok) {
        alert("✅ Username updated successfully!");
        // Update username on the page
        document.getElementById("userName").textContent = newUsername;
        document.getElementById("sidebarName").textContent = newUsername;
      } else {
        alert(
          `❌ Error updating username: ${data.message || response.statusText}`
        );
      }
    } catch (error) {
      console.error("Error updating username:", error);
      alert("An error occurred while updating the username.");
    }
  });

  const notifToggle = document.getElementById("notifToggle");

  // Fetch and set the initial state of the notification and language settings
  fetch("/api/settings")
    .then((res) => res.json())
    .then((data) => {
      notifToggle.checked = data.notifications;
      languageSelect.value = data.language;
    });

  languageSelect?.addEventListener("change", async () => {
    const language = languageSelect.value;
    try {
      const response = await fetch("/api/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ language: language }),
      });

      const data = await response.json();

      if (!response.ok) {
        alert(
          `❌ Error updating language settings: ${
            data.message || response.statusText
          }`
        );
      }
    } catch (error) {
      console.error("Error updating language settings:", error);
      alert("An error occurred while updating the language settings.");
    }
  });

  notifToggle?.addEventListener("change", async () => {
    const enabled = notifToggle.checked;
    try {
      const response = await fetch("/api/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ notifications: enabled }),
      });

      const data = await response.json();

      if (!response.ok) {
        alert(
          `❌ Error updating notification settings: ${
            data.message || response.statusText
          }`
        );
      }
    } catch (error)  {
      console.error("Error updating notification settings:", error);
      alert("An error occurred while updating the notification settings.");
    }
  });

  // --- Change Password ---
  const changePasswordForm = document.getElementById("changePasswordForm");
  changePasswordForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const currentPassword = document.getElementById("currentPassword").value;
    const newPassword = document.getElementById("newPassword").value;
    const confirmNewPassword = document.getElementById("confirmNewPassword").value;

    if (newPassword !== confirmNewPassword) {
      alert("New passwords do not match.");
      return;
    }

    if (!currentPassword || !newPassword) {
      alert("Please fill out all password fields.");
      return;
    }

    try {
      const response = await fetch("/api/security/change-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        alert("✅ Password changed successfully!");
        changePasswordForm.reset(); // Clear the form
      } else {
        alert(`❌ Error: ${data.error || "Failed to change password."}`);
      }
    } catch (error) {
      console.error("Password change error:", error);
      alert("An error occurred while changing the password.");
    }
  });


  // ---------------- TEMPLATES ----------------
  document.querySelectorAll("#templatesSection button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const templateName = btn.closest("div").querySelector("h3").textContent;
      // For now, let's just download a dummy file.
      // In a real application, you would fetch the template from the server.
      const blob = new Blob([`This is a dummy ${templateName} template.`], {
        type: "text/plain",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${templateName
        .toLowerCase()
        .replace(/\s+/g, "-")}-template.txt`;
      document.body.appendChild(a);
a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  });

  // ---------------- PROFILE FORM SUBMISSION ----------------
  profileForm?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const sanitize = (str) =>
      str.replace(/</g, "&lt;").replace(/>/g, "&gt;").trim();

    const name = sanitize(document.getElementById("profileName").value);
    const email = document.getElementById("profileEmail").value.trim();
    const phone = sanitize(document.getElementById("profilePhone").value);
    const location = sanitize(document.getElementById("profileLocation").value);
    const bio = sanitize(document.getElementById("profileBio").value);

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      alert("Invalid email format.");
      return;
    }

    try {
      const response = await fetch("/api/profile", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: name,
          email: email,
          phone: phone,
          location: location,
          bio: bio,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        alert("✅ Profile saved securely!");
        // Update displayed elements on the page
        profileDisplayElements.userName.textContent = name;
        profileDisplayElements.userEmail.textContent = email;
        profileDisplayElements.userBio.textContent = bio;
        profileDisplayElements.sidebarName.textContent = name;
        profileDisplayElements.userPhone.textContent = phone;
        profileDisplayElements.userLocation.textContent = location;

        profileForm.classList.add("hidden"); // Hide form after saving
        toggleEditProfileFormBtn.classList.remove("hidden"); // Show edit button
      } else {
        alert(
          `❌ Error saving profile: ${data.message || response.statusText}`
        );
      }
    } catch (error) {
      console.error("Error updating profile:", error);
      alert("An error occurred while saving profile.");
    }
  });

  // ---------------- AVATAR FORM SUBMISSION ----------------
  const avatarForm = document.getElementById("avatarForm");
  avatarForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const avatarInput = document.getElementById("avatarInput");
    const file = avatarInput.files[0];

    if (!file) {
      alert("Please select a file.");
      return;
    }

    const formData = new FormData();
    formData.append("avatar", file);

    try {
      const response = await fetch("/api/avatar/upload", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        alert("✅ Avatar updated successfully!");
        const newAvatarUrl = data.avatar_url;
        document.getElementById("sidebarAvatar").src = newAvatarUrl;
        document.getElementById("userAvatar").src = newAvatarUrl;
      } else {
        alert(
          `❌ Error uploading avatar: ${data.error || response.statusText}`
        );
      }
    } catch (error) {
      console.error("Error uploading avatar:", error);
      alert("An error occurred while uploading the avatar.");
    }
  });

  // ---------------- ACTIVITY LOG ----------------
  const activityLogContainer = document.getElementById("activityLogContainer");

  async function loadActivityLog() {
    activityLogContainer.innerHTML = `<p class="text-center text-gray-500 dark:text-gray-400">Loading activity...</p>`;

    try {
      const response = await fetch("/api/logs");
      if (!response.ok) {
        throw new Error(`Failed to fetch logs: ${response.statusText}`);
      }
      let logs = await response.json();

      // Filter logs to only include desired actions
      const filteredLogs = logs.filter((log) => {
        const lowerCaseAction = log.action.toLowerCase();
        return (
          lowerCaseAction.includes("file convert") ||
          lowerCaseAction.includes("file upload") ||
          lowerCaseAction.includes("file share") ||
          lowerCaseAction.includes("template use")
        );
      });

      if (filteredLogs.length === 0) {
        activityLogContainer.innerHTML = `<p class="text-center text-gray-500 dark:text-gray-400">No relevant activity recorded yet.</p>`;
      } else {
        activityLogContainer.innerHTML = filteredLogs
          .map(
            (log) => `
          <div class="flex items-start gap-4 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
            <div class="w-8 h-8 flex-shrink-0 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
              <i class="fa-solid ${getIconForAction(
                log.action
              )} text-gray-600 dark:text-gray-300"></i>
            </div>
            <div>
              <p class="font-medium text-gray-800 dark:text-gray-200">${
                log.action
              }</p>
              <p class="text-sm text-gray-600 dark:text-gray-400">${
                log.details
              }</p>
              <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">${new Date(
                log.timestamp
              ).toLocaleString()}</p>
            </div>
          </div>
        `
          )
          .join("");
      }
    } catch (error) {
      activityLogContainer.innerHTML = `<p class="text-center text-red-500">Error loading activity log.</p>`;
      console.error("Error fetching activity log:", error);
    }
  }

  // Initial load of the default section's content
  loadActivityLog();

  // Initial load of user files
  loadUserFiles();

  function getIconForAction(action) {
    if (action.includes("Login")) return "fa-right-to-bracket";
    if (action.includes("Logout")) return "fa-right-from-bracket";
    if (action.includes("Profile")) return "fa-user-pen";
    if (action.includes("File")) return "fa-file-arrow-up";
    return "fa-circle-info";
  }

  const filesListContainer = document.getElementById("filesListContainer");

  async function loadUserFiles() {
    const searchTerm = document.getElementById("fileSearchInput").value;
    const url = new URL(window.location.origin + "/api/files");
    if (searchTerm) {
      url.searchParams.append("search", searchTerm);
    }

    filesListContainer.innerHTML = `<p class="text-center text-gray-500 dark:text-gray-400">Loading your files...</p>`;

    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch files: ${response.statusText}`);
      }
      const files = await response.json();

      if (files.length === 0) {
        filesListContainer.innerHTML = `<p class="text-center text-gray-500 dark:text-gray-400">You haven't converted any files yet.</p>`;
      } else {
        filesListContainer.innerHTML = files
          .map(
            (file) => `
            <div class="p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 shadow-sm bg-white dark:bg-neutral-900 flex items-center justify-between" data-file-id="${
              file.id
            }">
              <div class="flex items-center gap-4">
                <div class="w-10 h-10 flex-shrink-0 rounded-lg bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
                  <i class="fa-solid fa-file-lines text-gray-600 dark:text-gray-300"></i>
                </div>
              <div>
                <h3 class="font-medium truncate max-w-xs">${
                  file.filename
                }</h3>
                <p class="text-sm text-neutral-500">
                  ${
                    file.format && file.format !== "shared"
                      ? `Converted to <strong>${file.format.toUpperCase()}</strong>`
                      : `Uploaded`
                  }
                  on ${new Date(file.timestamp).toLocaleDateString()}
                  <span class="ml-2 px-2 py-1 text-xs rounded-full ${
                    file.file_type === "temporary"
                      ? "bg-yellow-200 text-yellow-800"
                      : "bg-green-200 text-green-800"
                  }">${file.file_type}</span>
                  ${
                    file.file_type === "temporary" && file.expires_at
                      ? `<span class="ml-2 text-xs text-red-500">Expires on ${new Date(
                          file.expires_at
                        ).toLocaleDateString()}</span>`
                      : ""
                  }
                </p>
              </div>
            </div>
            <div class="flex gap-2">
              <a href="${
                file.url
              }" download class="p-2 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-neutral-100 dark:hover:bg-neutral-800" title="Download">
                <i class="fa-solid fa-download"></i>
              </a>
              <button class="share-file-btn p-2 rounded-lg text-blue-500 hover:bg-blue-100 dark:hover:bg-blue-900/50" title="Share" data-share-url="${file.share_url}">
                <i class="fa-solid fa-share-nodes pointer-events-none"></i>
              </button>
              <button class="delete-file-btn p-2 rounded-lg text-red-500 hover:bg-red-100 dark:hover:bg-red-900/50" title="Delete" data-file-id="${
                file.id
              }">
                <i class="fa-solid fa-trash-can pointer-events-none"></i>
              </button>
            </div>
          </div>
        `
          )
          .join("");
      }
    } catch (error) {
      filesListContainer.innerHTML = `<p class="text-center text-red-500">Error loading your files.</p>`;
      console.error("Error fetching user files:", error);
    }
  }

  // Event delegation for deleting files
  filesListContainer.addEventListener("click", async (e) => {
    // Handle Share Button
    const shareButton = e.target.closest(".share-file-btn");
    if (shareButton) {
      const shareUrl = shareButton.dataset.shareUrl;
      shareLinkInput.value = shareUrl;
      shareFileModal.classList.remove("hidden");
      return; // Stop further execution if share button was clicked
    }

    // Handle Delete Button
    const deleteButton = e.target.closest(".delete-file-btn");
    if (deleteButton) {
      const fileId = deleteButton.dataset.fileId;
      const fileCard = deleteButton.closest("[data-file-id]");
      const filename = fileCard.querySelector("h3").textContent;
  
      if (
        confirm(
          `Are you sure you want to delete "${filename}"? This action cannot be undone.`
        )
      ) {
        try {
          const response = await fetch(`/api/files/${fileId}`, {
            method: "DELETE",
          });
  
          const data = await response.json();
  
          if (response.ok) {
            fileCard.remove(); // Remove the file card from the UI
            alert(data.message);
          } else {
            throw new Error(data.error || "Failed to delete the file.");
          }
        } catch (error) {
          console.error("Deletion error:", error);
          alert(`Error: ${error.message}`);
        }
      }
    }
  });

  // --- File Search ---
  const fileSearchInput = document.getElementById("fileSearchInput");
  let debounceTimer;

  fileSearchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      // When the user types, we should reset the filesLoaded flag to force a reload
      // For simplicity, we just call the load function directly.
      loadUserFiles();
    }, 300); // Wait 300ms after user stops typing before searching
  });
});

// Tailwind CSS Dark Mode Configuration
tailwind.config = {
  darkMode: "class",
};