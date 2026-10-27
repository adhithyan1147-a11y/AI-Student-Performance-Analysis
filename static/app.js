document.addEventListener("DOMContentLoaded", () => {
  const list = document.getElementById("subjects-list");
  const add = document.getElementById("add-subject");
  if (!list || !add) return;
  const attachRemove = (row) => {
    const button = row.querySelector(".remove-subject");
    if (button) button.addEventListener("click", () => {
      if (list.querySelectorAll(".subject-row").length <= 1) {
        alert("At least one subject is required.");
        return;
      }
      row.remove();
    });
  };
  list.querySelectorAll(".subject-row").forEach(attachRemove);
  add.addEventListener("click", () => {
    const row = document.createElement("div");
    row.className = "subject-row";
    row.innerHTML = '<label>Subject<input name="subject[]" required placeholder="Subject name"></label><label>Mark (0–100)<input name="mark[]" type="number" min="0" max="100" step="0.01" required></label><button type="button" class="remove-subject secondary">Remove</button>';
    list.appendChild(row);
    attachRemove(row);
    row.querySelector("input").focus();
  });
});
