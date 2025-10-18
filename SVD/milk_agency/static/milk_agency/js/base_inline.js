function updateDateTime() {
  const now = new Date();

  // Format Date (DD-MM-YYYY)
  const date = now.toLocaleDateString("en-GB"); // e.g. 30/08/2025

  // Format Time (HH:MM:SS)
  const time = now.toLocaleTimeString("en-US", { hour12: true }); // 12-hour format with AM/PM
  // If you want 24-hour format, use:
  // const time = now.toLocaleTimeString("en-GB");

  document.getElementById("date").textContent = date;
  document.getElementById("time").textContent = time;
}

// Run immediately and update every second
updateDateTime();
setInterval(updateDateTime, 1000);
