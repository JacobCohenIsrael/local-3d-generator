// Native disclosures remain usable without JavaScript; add light dismissal behavior.
const helpBoxes = [...document.querySelectorAll('.field-help')];
for (const box of helpBoxes) box.addEventListener('toggle', () => {
  box.classList.remove('opens-up');
  if (!box.open) return;
  const panel = box.querySelector('.help-box').getBoundingClientRect();
  const label = box.parentElement.getBoundingClientRect();
  if (panel.bottom > window.innerHeight - 12 && label.top > panel.height + 12) box.classList.add('opens-up');
});
document.addEventListener('click', event => {
  for (const box of helpBoxes) if (box.open && !box.contains(event.target)) box.open = false;
});
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  for (const box of helpBoxes) if (box.open) {
    box.open = false;
    box.querySelector('summary').focus();
    event.preventDefault();
  }
});
