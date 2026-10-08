'use strict';
const $ = id => document.getElementById(id);
const tactics = ['urgency', 'fear', 'authority', 'reward', 'trust', 'payment_pressure'];
const labels = {urgency:'Urgency',fear:'Fear',authority:'Authority',reward:'Reward',trust:'Trust',payment_pressure:'Payment pressure',action:'Action'};
const colors = {urgency:'#fbbf24',fear:'#f87171',authority:'#38bdf8',reward:'#c4b5fd',trust:'#34d399',payment_pressure:'#f59e0b'};
const state = {messages:[], records:[], selected:null, dna:null, victim:null, training:null, generation:0, pending:false};
const element = (tag, text, className) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; };
const showNotice = message => { $('global-status').textContent = message; $('global-status').hidden = !message; };
const errorText = data => typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map(item => `${item.loc?.slice(1).join('.') || 'Input'}: ${item.msg}`).join('; ') : data.error || 'Request could not be completed.';
async function api(path, payload) {
  const response = await fetch(path, {method:payload === undefined ? 'GET' : 'POST', headers:payload === undefined ? {} : {'Content-Type':'application/json'}, ...(payload === undefined ? {} : {body:JSON.stringify(payload)})});
  const data = await response.json();
  if (!response.ok) throw new Error(errorText(data));
  return data;
}
function validateDNA(dna) {
  if (!dna || !dna.id || !dna.source_message_id || !dna.campaign_id || !dna.extraction_model || Number.isNaN(Date.parse(dna.created_at))) throw new Error('DNA response is missing provenance.');
  if (!dna.tactics || Object.keys(dna.tactics).sort().join() !== [...tactics].sort().join() || tactics.some(t => !Number.isInteger(dna.tactics[t]) || dna.tactics[t] < 0 || dna.tactics[t] > 100)) throw new Error('DNA response has invalid tactic scores.');
  if (!Array.isArray(dna.attack_chain) || !dna.attack_chain.length || new Set(dna.attack_chain).size !== dna.attack_chain.length || dna.attack_chain.some(t => ![...tactics,'action'].includes(t))) throw new Error('DNA response has an invalid attack chain.');
  if (['similarity','confidence'].some(key => typeof dna[key] !== 'number' || !Number.isFinite(dna[key]) || dna[key] < 0 || dna[key] > 1)) throw new Error('DNA response has invalid confidence or similarity.');
  if (['phones','domains','wallets','payment_links'].some(key => !Array.isArray(dna.iocs?.[key]) || dna.iocs[key].some(value => typeof value !== 'string'))) throw new Error('DNA response has invalid indicators.');
  return dna;
}
function drawBars(target, scores) {
  target.replaceChildren();
  for (const tactic of tactics) {
    const row = element('div',undefined,'tactic-row'), track = element('div',undefined,'bar-track'), fill = element('div',undefined,'bar-fill');
    track.setAttribute('role','meter'); track.setAttribute('aria-label',labels[tactic]); track.setAttribute('aria-valuemin','0'); track.setAttribute('aria-valuemax','100'); track.setAttribute('aria-valuenow',String(scores[tactic]));
    fill.style.width = `${scores[tactic]}%`; fill.style.background = colors[tactic]; track.append(fill);
    row.append(element('span',labels[tactic],'tactic-label'),track,element('span',String(scores[tactic]),'bar-number')); target.append(row);
  }
}
function drawDNA(dna) {
  state.dna = null; $('dna-content').hidden = true; $('dna-empty').hidden = false; $('dna-badges').replaceChildren(); $('train-this-button').disabled = true;
  if (!dna) return;
  validateDNA(dna); state.dna = dna;
  $('dna-provenance').textContent = `${dna.id} · ${dna.extraction_model === 'curated/reference' ? 'Curated reference scenario' : 'Extracted from selected message'}`;
  $('dna-badges').append(element('span',`${Math.round(dna.similarity*100)}% match to #${dna.campaign_id.replace(/^camp_/, '')}`,'badge match'),element('span',`Confidence ${Math.round(dna.confidence*100)}%`,'badge confidence'));
  drawBars($('tactic-bars'),dna.tactics); drawBars($('budget-bars'),dna.tactics);
  $('attack-chain').replaceChildren(); dna.attack_chain.forEach((tactic,index) => { if (index) { const arrow = element('li','→','chain-arrow'); arrow.setAttribute('aria-hidden','true'); arrow.style.animationDelay = `${index*250}ms`; $('attack-chain').append(arrow); } const node = element('li',labels[tactic],'chain-node'); node.style.animationDelay = `${index*250}ms`; $('attack-chain').append(node); });
  $('ioc-list').replaceChildren(); for (const [key,title] of [['phones','Phones'],['domains','Domains'],['wallets','Wallets'],['payment_links','Payment links']]) { const group = element('div',undefined,'ioc-group'); group.append(element('strong',title)); for (const value of dna.iocs[key].length ? dna.iocs[key] : ['None observed']) group.append(element('div',value,'ioc-value')); $('ioc-list').append(group); }
  $('dna-model').textContent = `${dna.extraction_model} · ${new Date(dna.created_at).toISOString().replace('T',' ').slice(0,19)} UTC`;
  $('dna-content').hidden = false; $('dna-empty').hidden = true; $('train-this-button').disabled = false;
}
function renderInbox() {
  $('message-list').replaceChildren(); $('corpus-count').textContent = String(state.messages.length);
  for (const message of state.messages) { const button = element('button',undefined,`message-item${state.selected?.id === message.id ? ' selected' : ''}`); button.setAttribute('aria-pressed',String(state.selected?.id === message.id)); button.append(element('strong',message.sender.replaceAll('_',' ')),element('span',message.text)); button.addEventListener('click',() => selectMessage(message)); $('message-list').append(button); }
}
function selectMessage(message) {
  state.selected = message; state.victim = null; $('source-text').textContent = message.text; $('source-id').textContent = message.id; $('source-channel').textContent = message.channel; $('scan-status').hidden = true; $('inspect-button').disabled = false; $('start-victim').disabled = false;
  $('victim-transcript').replaceChildren(element('p','Start with the selected message, then supply simulated inbound replies.','muted small')); $('victim-state').textContent = ''; $('victim-text').disabled = $('victim-send').disabled = true;
  const records = state.records.filter(dna => dna.source_message_id === message.id).sort((a,b) => Date.parse(b.created_at)-Date.parse(a.created_at));
  drawDNA(records[0] || null); renderInbox();
}
function drawVerdict(verdict) {
  const blocked = verdict.injection || verdict.needs_review;
  $('scan-status').hidden = false; $('scan-status').className = `scan-status${blocked ? ' blocked' : verdict.is_scam ? '' : ' clean'}`;
  $('scan-status').textContent = verdict.injection ? `Injection refused. ${verdict.deflection}` : verdict.needs_review ? `Paused for review: ${verdict.reason}` : verdict.is_scam ? `Scam cues detected. ${verdict.tactic_hints.map(t => labels[t]).join(', ')}.` : 'No scam cues detected in this inspection.';
}
function switchView(training) {
  if (training && !state.dna && !state.training) { showNotice('Select and inspect a scam message before starting practice.'); return; }
  $('analysis-view').hidden = training; $('training-view').hidden = !training;
  $('nav-analysis').classList.toggle('selected',!training); $('nav-training').classList.toggle('selected',training);
  for (const [id,selected] of [['nav-analysis',!training],['nav-training',training]]) { if (selected) $(id).setAttribute('aria-current','page'); else $(id).removeAttribute('aria-current'); }
  if (training) $('training-source').textContent = `Based on ${state.training?.dna.id || state.dna.id} · same chain, new disguise`;
  showNotice('');
}
function drawVictim(session) {
  state.victim = session; $('victim-transcript').replaceChildren();
  for (const turn of session.turns) { const node = element('div',undefined,'victim-turn'); node.append(element('strong',`Simulated inbound · turn ${turn.turn}`),element('p',turn.scammer),element('strong',turn.sentinel.injection ? 'Margaret · injection refused' : 'Margaret',turn.sentinel.injection ? 'refusal' : ''),element('p',turn.victim)); $('victim-transcript').append(node); }
  $('victim-state').textContent = `${session.status} · observed: ${session.tactic_history.map(t => labels[t]).join(', ') || 'no new tactics'}`;
  $('victim-text').disabled = $('victim-send').disabled = session.status !== 'active'; $('victim-transcript').scrollTop = $('victim-transcript').scrollHeight;
}
function drawTraining(session) {
  state.training = session; localStorage.setItem('honeypot-session',session.session_id);
  $('training-consent').hidden = true; $('training-source').textContent = `Based on ${session.dna.id} · variant ${session.variant_id}`;
  drawBars($('budget-bars'),validateDNA(session.dna).tactics);
  const viewport = $('chat-messages'), atBottom = viewport.scrollHeight-viewport.scrollTop-viewport.clientHeight < 80;
  viewport.replaceChildren(); for (const message of session.messages) { const node = element('div',undefined,`bubble${message.role === 'user' ? ' user' : ''}`); node.append(element('span',message.role === 'user' ? 'You' : 'Fictional counterpart','role-label'),element('span',message.text)); viewport.append(node); }
  if (atBottom) viewport.scrollTop = viewport.scrollHeight;
  const active = session.status === 'active'; $('chat-text').disabled = $('chat-send').disabled = !active || state.pending; $('training-end').disabled = !!session.report;
  $('training-stage').textContent = active ? `Stage ${session.cursor+1}/${session.dna.attack_chain.length}: ${labels[session.dna.attack_chain[session.cursor]]}` : 'Session ended';
  $('chat-progress').textContent = state.pending ? 'Counterpart is responding…' : `${session.counterpart_messages}/8 counterpart messages · Enter to send`;
  if (session.report) drawReport(session.report);
}
function drawReport(report) {
  const current = state.training;
  if (!current || report.user_session !== current.session_id || report.trained_on !== current.dna.id || report.variant_id !== current.variant_id || !Number.isInteger(report.immunity_score) || report.immunity_score < 0 || report.immunity_score > 100 || !Array.isArray(report.scores) || !report.scores.length || report.scores.some(row => !tactics.includes(row.tactic) || !['strong','medium','weak'].includes(row.result) || typeof row.note !== 'string') || !Array.isArray(report.coaching) || !report.coaching.length || report.coaching.some(line => typeof line !== 'string') || report.disclaimer !== 'Training metric, not a scientifically validated probability of avoiding a real-world scam.') throw new Error('Invalid immunity report; no score will be displayed.');
  $('report-score').textContent = String(report.immunity_score); $('report-scores').replaceChildren();
  for (const row of report.scores) { const block = element('div',undefined,'score-row'), head = element('div',undefined,'score-row-head'); head.append(element('span',labels[row.tactic]),element('span',row.result,'result-label '+row.result)); block.append(head,element('p',row.note,'score-note')); $('report-scores').append(block); }
  $('report-coaching').replaceChildren(...report.coaching.map(line => element('p',line))); $('report-disclaimer').textContent = report.disclaimer; $('report-ids').textContent = `${report.user_session} · ${report.trained_on} · ${report.variant_id}`;
  $('report-content').hidden = false; $('report-empty').hidden = true; $('practice-again').hidden = false; $('report-heading').focus();
}
function resetPractice() {
  if (state.training?.status === 'active') { trainingError('End the current drill before starting another.'); return; }
  state.generation++; state.training = null; state.pending = false; localStorage.removeItem('honeypot-session'); $('training-consent').hidden = false; $('training-agree').checked = false; $('training-start').disabled = true; $('chat-messages').replaceChildren(); $('report-content').hidden = true; $('report-empty').hidden = false; $('training-error').hidden = true; $('practice-again').hidden = true; $('training-stage').textContent = 'Not started'; $('training-end').disabled = true; $('chat-text').disabled = $('chat-send').disabled = true;
  if (state.dna) { $('training-source').textContent = `Based on ${state.dna.id} · same chain, new disguise`; drawBars($('budget-bars'),state.dna.tactics); }
}
function trainingError(message) { $('training-error').textContent = message; $('training-error').hidden = false; }
$('nav-analysis').onclick = $('back-to-dna').onclick = () => switchView(false);
$('nav-training').onclick = $('train-this-button').onclick = () => switchView(true);
$('inspect-button').onclick = async () => { const button = $('inspect-button'), message = state.selected; button.disabled = true; try { const result = await api('/intake',{message,synthetic:true}); if (result.dna) state.records = [...state.records.filter(dna => dna.id !== result.dna.id),result.dna]; if (state.selected?.id !== message.id) return; drawVerdict(result.verdict); drawDNA(result.dna); showNotice(''); } catch (error) { if (state.selected?.id === message.id) { drawDNA(null); showNotice(error.message); } } finally { button.disabled = false; } };
$('paste-form').onsubmit = async event => { event.preventDefault(); const button = event.submitter; button.disabled = true; try { const result = await api('/analyze',{text:$('paste-text').value,synthetic:$('paste-consent').checked}); state.messages.push(result.message); if (result.dna) state.records.push(result.dna); selectMessage(result.message); drawVerdict(result.verdict); $('paste-text').value = ''; showNotice(''); } catch (error) { showNotice(error.message); } finally { button.disabled = false; } };
$('start-victim').onclick = async () => { $('start-victim').disabled = true; try { drawVictim((await api('/engage/start',{message_id:state.selected.id})).session); showNotice(''); } catch (error) { showNotice(error.message); } finally { $('start-victim').disabled = false; } };
$('victim-form').onsubmit = async event => { event.preventDefault(); $('victim-send').disabled = true; try { drawVictim((await api('/engage/step',{session_id:state.victim.session_id,text:$('victim-text').value,synthetic:true})).session); $('victim-text').value = ''; showNotice(''); } catch (error) { showNotice(error.message); } finally { $('victim-send').disabled = state.victim?.status !== 'active'; } };
$('training-agree').onchange = () => { $('training-start').disabled = !$('training-agree').checked || !state.dna; };
$('training-start').onclick = async () => { $('training-start').disabled = true; $('training-error').hidden = true; try { const result = await api('/train/start',{dna_id:state.dna.id,consent:$('training-agree').checked}); drawTraining(result.session); $('chat-text').focus(); } catch (error) { trainingError(error.message); $('training-start').disabled = !$('training-agree').checked; } };
$('chat-form').onsubmit = async event => { event.preventDefault(); if (!state.training || state.pending || state.training.status !== 'active') return; const ticket = state.generation, text = $('chat-text').value; state.pending = true; drawTraining(state.training); $('training-error').hidden = true; try { const result = await api('/train/message',{session_id:state.training.session_id,text,synthetic:true}); if (ticket !== state.generation) return; state.pending = false; drawTraining(result.session); $('chat-text').value = ''; if (result.session.status === 'active') $('chat-text').focus(); } catch (error) { if (ticket === state.generation) { state.pending = false; drawTraining(state.training); trainingError(error.message+' Your reply was not accepted. Edit it or retry.'); } } };
$('chat-text').onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); if (!$('chat-send').disabled) $('chat-form').requestSubmit(); } };
$('training-end').onclick = async () => { if (!state.training) return; state.generation++; state.pending = false; state.training.status = 'completed'; drawTraining(state.training); $('training-end').disabled = true; $('training-error').hidden = true; try { const result = await api('/train/end',{session_id:state.training.session_id}); state.training.report = result.report; drawReport(result.report); } catch (error) { trainingError(error.message); $('training-end').disabled = false; $('practice-again').hidden = false; } };
$('practice-again').onclick = resetPractice;
async function initialize() {
  try { const [health,corpus,dna] = await Promise.all([api('/health'),api('/corpus'),api('/dna')]); $('mode-badge').textContent = health.mode === 'rehearsal' ? 'Scripted rehearsal · no model calls' : `Featherless ${health.cache_only ? '· cached replay' : '· live'}`; state.messages = corpus.messages; state.records = dna.dna_records.map(validateDNA); const initial = state.messages.find(message => message.id === 'msg_117') || state.messages[0]; if (initial) selectMessage(initial); else renderInbox(); if (health.mode === 'live' && !health.model_configured && !health.cache_only) showNotice('Featherless is not configured. New model requests will pause for review; setup is in the README.'); const saved = localStorage.getItem('honeypot-session'); if (saved) { try { drawTraining((await api(`/train/${encodeURIComponent(saved)}`)).session); } catch { localStorage.removeItem('honeypot-session'); } } } catch (error) { showNotice(`Application unavailable: ${error.message} Reload after resolving the error.`); $('mode-badge').textContent = 'Unavailable'; }
}
initialize();
