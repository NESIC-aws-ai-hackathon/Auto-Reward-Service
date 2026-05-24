const tabs = document.querySelectorAll('.tab');
const pages = document.querySelectorAll('.page');

function showPage(name){
  pages.forEach(p=>p.classList.toggle('active', p.dataset.page===name));
  tabs.forEach(t=>t.classList.toggle('active', t.dataset.target===name && !t.classList.contains('center')));
  localStorage.setItem('furemaru_page', name);
}

tabs.forEach(tab=>tab.addEventListener('click',()=>showPage(tab.dataset.target)));

const last = localStorage.getItem('furemaru_page');
if(last && document.querySelector(`[data-page="${last}"]`)) showPage(last);

const textToggle = document.getElementById('textToggle');
const textInputPanel = document.getElementById('textInputPanel');
if(textToggle){
  textToggle.addEventListener('change',()=>{textInputPanel.hidden=!textToggle.checked;});
}

document.querySelectorAll('.quick-card').forEach(btn=>btn.addEventListener('click',()=>{
  showPage('chat');
  if(textToggle && textInputPanel){textToggle.checked=true;textInputPanel.hidden=false;}
  const input = document.getElementById('chatInput');
  input.value = btn.dataset.fill || '';
  input.focus();
}));

/*
  GitHub Copilot 向けメモ:
  感情差分のアバターは ./assets/emotions/ 配下を使う前提です。
  例:
  - happy.png    : 明るく励ます返答
  - support.png  : 寄り添い・共感
  - shy.png      : やさしい案内
  - excited.png  : ごほうびや達成演出
  - neutral.png  : 通常状態
  - listening.png: 音声待機・リスニング状態
*/
function getEmotionAvatarPath(emotion='neutral'){
  const table = {
    neutral: './assets/emotions/neutral.png',
    happy: './assets/emotions/happy.png',
    support: './assets/emotions/support.png',
    shy: './assets/emotions/shy.png',
    excited: './assets/emotions/excited.png',
    listening: './assets/emotions/listening.png'
  };
  return table[emotion] || table.neutral;
}

function appendAssistantMessage({text, emotion='support'}){
  const thread=document.querySelector('.chat-thread');
  const now=new Date();
  const h=String(now.getHours()).padStart(2,'0');
  const m=String(now.getMinutes()).padStart(2,'0');
  const reply=document.createElement('article');
  reply.className='message assistant';
  reply.innerHTML=`<img src="${getEmotionAvatarPath(emotion)}" alt="" class="emotion-avatar" data-emotion="${emotion}"><div><small>ふれまーるちゃん</small><p>${escapeHtml(text)}</p></div><time>${h}:${m}</time>`;
  thread.appendChild(reply);
  reply.scrollIntoView({behavior:'smooth', block:'end'});
}

const sendButton = document.getElementById('sendButton');
if(sendButton){
  sendButton.addEventListener('click',()=>{
    const input=document.getElementById('chatInput');
    const text=input.value.trim();
    if(!text) return;
    const thread=document.querySelector('.chat-thread');
    const now=new Date();
    const h=String(now.getHours()).padStart(2,'0');
    const m=String(now.getMinutes()).padStart(2,'0');

    const user=document.createElement('article');
    user.className='message user';
    user.innerHTML=`<p>${escapeHtml(text)}</p><time>${h}:${m}</time>`;
    thread.appendChild(user);

    appendAssistantMessage({
      text:'うんうん、教えてくれてありがとう。今日はその気持ちも、やさしく記録しておくね。',
      emotion:'support'
    });

    input.value='';
  });
}

const micButton=document.getElementById('micButton');
if(micButton){
  micButton.addEventListener('click',()=>{
    micButton.classList.toggle('recording');
    micButton.querySelector('span').textContent = micButton.classList.contains('recording') ? '⏹' : '🎙';
  });
}

function escapeHtml(s){
  return s.replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

if('serviceWorker' in navigator){
  window.addEventListener('load',()=>navigator.serviceWorker.register('./sw.js').catch(()=>{}));
}
