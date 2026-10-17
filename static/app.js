(() => {
  const clock = document.getElementById('clock');
  if (clock) { const tick = () => { clock.textContent = new Date().toLocaleTimeString('ko-KR', {hour12:false}); }; tick(); setInterval(tick, 1000); }
  const form = document.getElementById('mes-form');
  if (!form) return;
  const plan = document.getElementById('plan_id');
  if (plan) plan.addEventListener('change', () => {
    const match = plan.options[plan.selectedIndex]?.text.match(/계획\s*([\d,]+)/);
    const quantity = document.getElementById('order_qty');
    if (match && quantity) quantity.value = match[1].replaceAll(',', '');
  });
  const select = document.getElementById('work_order_id');
  if (!select) return;
  const orderText = document.getElementById('selected-product');
  const qtyText = document.getElementById('selected-qty');
  const produced = document.getElementById('produced_qty');
  const defect = document.getElementById('defect_qty');
  const refresh = () => {
    const option = select.options[select.selectedIndex];
    const label = option && option.value ? option.text : '';
    const match = label.match(/·\s*(.*?)\s*·\s*지시\s*([\d,]+)/);
    if (orderText) orderText.textContent = match ? match[1] : '작업지시를 선택하세요';
    if (qtyText) qtyText.textContent = match ? `${match[2]} 개` : '—';
    const p = Number(produced?.value || 0), d = Number(defect?.value || 0), q = Number((match?.[2] || '0').replaceAll(',', ''));
    const good = document.getElementById('good-preview'), attain = document.getElementById('attainment-preview'), rate = document.getElementById('defect-preview');
    if (good) good.textContent = `${Math.max(0,p-d)} 개`;
    if (attain) attain.textContent = `${q ? (p/q*100).toFixed(1) : '0.0'}%`;
    if (rate) rate.textContent = `${p ? (d/p*100).toFixed(2) : '0.00'}%`;
  };
  [select, produced, defect].filter(Boolean).forEach(el => el.addEventListener('input', refresh));
  [select, produced, defect].filter(Boolean).forEach(el => el.addEventListener('change', refresh));
  refresh();
})();
