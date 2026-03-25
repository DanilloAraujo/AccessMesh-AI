import { useEffect, useState } from 'react';

// ---------------------------------------------------------------------------
// Translation dictionary
// ---------------------------------------------------------------------------
const translations: Record<string, Record<string, string>> = {
    // --- App shell ---
    'app.loading': { en: 'Loading…', pt: 'Carregando…' },
    'app.loadingPage': { en: 'Loading page', pt: 'Carregando página' },

    // --- Auth / loading state ---
    'auth.loading': { en: 'Loading…', pt: 'Carregando…' },
    'auth.signingIn': { en: 'Signing in…', pt: 'Entrando…' },
    'auth.signOut': { en: 'Sign Out', pt: 'Sair' },

    // --- Login page ---
    'login.title': { en: 'AccessMesh AI', pt: 'AccessMesh AI' },
    'login.subtitle': {
        en: 'Sign in to your AccessMesh AI account',
        pt: 'Acesse sua conta AccessMesh AI',
    },
    'login.email': { en: 'Email', pt: 'E-mail' },
    'login.emailPlaceholder': { en: 'your@email.com', pt: 'seu@email.com' },
    'login.password': { en: 'Password', pt: 'Senha' },
    'login.passwordPlaceholder': { en: '••••••••', pt: '••••••••' },
    'login.showPassword': { en: 'Show password', pt: 'Mostrar senha' },
    'login.hidePassword': { en: 'Hide password', pt: 'Ocultar senha' },
    'login.submit': { en: 'Sign In', pt: 'Entrar' },
    'login.submitting': { en: 'Signing in…', pt: 'Entrando…' },
    'login.noAccount': { en: "Don't have an account?", pt: 'Não tem conta?' },
    'login.register': { en: 'Create account', pt: 'Criar conta' },
    'login.error': { en: 'Invalid email or password.', pt: 'E-mail ou senha inválidos.' },
    'login.errorFallback': { en: 'Login failed.', pt: 'Falha no login.' },
    'login.responsible': {
        en: 'AccessMesh AI uses AI responsibly to promote accessibility.',
        pt: 'AccessMesh AI usa IA com responsabilidade para promover acessibilidade.',
    },

    // --- Register page ---
    'register.title': { en: 'Create Account', pt: 'Criar Conta' },
    'register.subtitle': { en: 'Welcome to AccessMesh AI', pt: 'Bem-vindo ao AccessMesh AI' },
    'register.name': { en: 'Name', pt: 'Nome' },
    'register.nameLabel': { en: 'Display Name', pt: 'Nome de exibição' },
    'register.namePlaceholder': { en: 'Your name', pt: 'Seu nome' },
    'register.namePlaceholderFull': { en: 'What should we call you?', pt: 'Como quer ser chamado(a)?' },
    'register.email': { en: 'Email', pt: 'E-mail' },
    'register.emailPlaceholder': { en: 'your@email.com', pt: 'seu@email.com' },
    'register.password': { en: 'Password', pt: 'Senha' },
    'register.passwordHint': { en: '(min. 8 characters)', pt: '(mín. 8 caracteres)' },
    'register.passwordTooShort': { en: 'Password must be at least 8 characters.', pt: 'A senha deve ter pelo menos 8 caracteres.' },
    'register.passwordPlaceholder': { en: '••••••••', pt: '••••••••' },
    'register.language': { en: 'Preferred Language', pt: 'Idioma Preferido' },
    'register.mode': { en: 'Communication Mode', pt: 'Modo de Comunicação' },
    'register.modeQuestion': { en: 'How do you prefer to communicate?', pt: 'Como prefere se comunicar?' },
    'register.modeHint': { en: '(can be changed later)', pt: '(pode mudar depois)' },
    'register.submit': { en: 'Register', pt: 'Registrar' },
    'register.submitLabel': { en: 'Create account', pt: 'Criar conta' },
    'register.submitting': { en: 'Creating account…', pt: 'Criando conta…' },
    'register.hasAccount': { en: 'Already have an account?', pt: 'Já tem conta?' },
    'register.login': { en: 'Sign In', pt: 'Entrar' },
    'register.errorFallback': { en: 'Registration failed.', pt: 'Falha no cadastro.' },
    'register.error': {
        en: 'Error creating account. Try again.',
        pt: 'Erro ao criar conta. Tente novamente.',
    },

    // --- Communication modes ---
    'mode.voice': { en: 'Voice', pt: 'Voz' },
    'mode.text': { en: 'Text', pt: 'Texto' },
    'mode.libras': { en: 'ASL', pt: 'Libras' },
    'mode.voice.send': { en: 'Speaks', pt: 'Fala' },
    'mode.voice.receive': { en: 'Listens', pt: 'Ouve' },
    'mode.voice.description': {
        en: 'Use microphone to speak in the meeting',
        pt: 'Use o microfone para falar na reunião',
    },
    'mode.text.send': { en: 'Types', pt: 'Digita' },
    'mode.text.receive': { en: 'Reads', pt: 'Lê' },
    'mode.text.description': {
        en: 'Type messages during the meeting',
        pt: 'Digite mensagens durante a reunião',
    },

    // --- Language options ---
    'lang.en': { en: 'English (US)', pt: 'Inglês (EUA)' },
    'lang.pt': { en: 'Portuguese (BR)', pt: 'Português (BR)' },

    // --- Home page ---
    'home.greeting': { en: 'Hello', pt: 'Olá' },
    'home.subtitle': {
        en: 'Select your communication mode and join a meeting',
        pt: 'Selecione seu modo de comunicação e entre em uma reunião',
    },
    'home.fullSubtitle': {
        en: 'Accessible multimodal communication — voice, gestures and text in one place.',
        pt: 'Comunicação multimodal acessível — voz, gestos e texto em um só lugar.',
    },
    'home.mode': { en: 'Communication Mode', pt: 'Modo de Comunicação' },
    'home.modeQuestion': { en: 'How do you want to communicate in this session?', pt: 'Como deseja se comunicar nesta sessão?' },
    'home.savingMode': { en: 'Saving…', pt: 'Salvando...' },
    'home.modeSend': { en: 'Sends: ', pt: 'Envia: ' },
    'home.modeReceive': { en: 'Receives: ', pt: 'Recebe: ' },
    'home.language': { en: 'Language', pt: 'Idioma' },
    'home.sessionId': { en: 'Meeting ID', pt: 'ID da Reunião' },
    'home.sessionIdPlaceholder': {
        en: 'Leave blank to create new',
        pt: 'Deixe em branco para criar nova',
    },
    'home.newRoom': { en: 'New Room', pt: 'Nova Sala' },
    'home.orJoin': { en: 'or join an existing room', pt: 'ou entre em uma sala existente' },
    'home.roomCode': { en: 'Room code', pt: 'Código da sala' },
    'home.joinButton': { en: 'Join Meeting', pt: 'Entrar na Reunião' },
    'home.joining': { en: 'Joining…', pt: 'Entrando…' },
    'home.logout': { en: 'Sign out', pt: 'Sair da conta' },
    'home.responsible': {
        en: 'By using AccessMesh AI, you agree to our responsible use of AI for accessibility.',
        pt: 'Ao usar o AccessMesh AI, você concorda com nosso uso responsável de IA para acessibilidade.',
    },

    // Mode cards (full descriptions for Home page)
    'mode.text.sendFull': { en: 'Type messages', pt: 'Digite mensagens' },
    'mode.text.receiveFull': { en: 'Receive in chat panel', pt: 'Receba no painel de chat' },
    'mode.libras.sendFull': { en: 'Camera captures your signs', pt: 'Câmera captura seus gestos' },
    'mode.libras.receiveFull': { en: 'Text in live transcription', pt: 'Texto em transcrição ao vivo' },
    'mode.voice.sendFull': { en: 'Microphone captures your voice', pt: 'Microfone captura sua fala' },
    'mode.voice.receiveFull': { en: 'Text in live transcription', pt: 'Texto em transcrição ao vivo' },

    // --- Meeting room ---
    'meeting.consentTitle': {
        en: 'Responsible AI Notice',
        pt: 'Aviso de IA Responsável',
    },
    'meeting.consentBody': {
        en: 'AccessMesh AI uses artificial intelligence to process voice, text, and sign language to promote inclusive communication. Your data is processed securely and is not shared with third parties.',
        pt: 'O AccessMesh AI usa inteligência artificial para processar voz, texto e linguagem de sinais para promover comunicação inclusiva. Seus dados são processados com segurança e não são compartilhados com terceiros.',
    },
    'meeting.consentAccept': { en: 'Accept and Enter', pt: 'Aceitar e Entrar' },
    'meeting.consentDecline': { en: 'Decline', pt: 'Recusar' },
    'meeting.aiBanner': {
        en: 'AI features are active in this meeting for transcription, translation, and sign language.',
        pt: 'Recursos de IA estão ativos nesta reunião para transcrição, tradução e linguagem de sinais.',
    },
    'meeting.sessionId': { en: 'Meeting ID', pt: 'ID da Reunião' },
    'meeting.copy': { en: 'Copy', pt: 'Copiar' },
    'meeting.copied': { en: 'Copied!', pt: 'Copiado!' },
    'meeting.leave': { en: 'Leave Meeting', pt: 'Sair da Reunião' },
    'meeting.micMode': {
        en: 'Your voice is being captured. Speak clearly.',
        pt: 'Sua voz está sendo capturada. Fale claramente.',
    },
    'meeting.textMode': {
        en: 'Type your message below and press Send.',
        pt: 'Digite sua mensagem abaixo e pressione Enviar.',
    },
    'meeting.librasMode': {
        en: 'Your webcam is capturing your signs.',
        pt: 'Sua webcam está capturando seus sinais.',
    },
    'meeting.sendMessage': { en: 'Send', pt: 'Enviar' },
    'meeting.sendBtnLabel': { en: 'Send message', pt: 'Enviar mensagem' },
    'meeting.messagePlaceholder': { en: 'Type a message…', pt: 'Digite uma mensagem…' },
    'meeting.messageLabel': { en: 'Type your message', pt: 'Digite sua mensagem' },
    'meeting.summaryButton': { en: 'Summary', pt: 'Resumo' },
    'meeting.genSummary': { en: 'Generate Minutes', pt: 'Gerar Ata' },
    'meeting.genSummaryLabel': { en: 'Generate Meeting Minutes', pt: 'Gerar Ata da Reunião' },
    'meeting.copyLink': { en: 'Copy room link', pt: 'Copiar link da sala' },
    'meeting.librasModeTitle': { en: 'ASL Mode', pt: 'Modo Libras' },
    'meeting.librasModeDesc': { en: 'Use the Gesture Camera on the side to capture and send your signs.', pt: 'Use a Gesture Camera ao lado para capturar e enviar seus sinais.' },
    'meeting.textModeTitle': { en: 'Text Mode', pt: 'Modo Texto' },
    'meeting.textModeDesc': { en: 'Use the side panel to send and receive messages.', pt: 'Use o painel lateral para enviar e receber mensagens.' },
    'meeting.voiceActive': { en: 'Recording…', pt: 'Gravando…' },
    'meeting.voiceInactive': { en: 'Microphone inactive', pt: 'Microfone inativo' },
    'meeting.voiceActiveDesc': { en: 'Your voice is being transcribed in real time.', pt: 'Sua voz está sendo transcrita em tempo real.' },
    'meeting.voiceInactiveDesc': { en: 'Click the button below to start recording.', pt: 'Clique no botão abaixo para começar a gravar.' },
    'meeting.voiceStopBtn': { en: 'Stop recording', pt: 'Parar gravação' },
    'meeting.voiceStartBtn': { en: 'Start recording', pt: 'Iniciar gravação' },

    // Consent modal (camera / mic permission)
    'consent.camera.title': { en: 'Camera Permission', pt: 'Permissão de Câmera' },
    'consent.camera.desc': { en: 'AccessMesh AI needs camera access to:', pt: 'A AccessMesh-AI precisa de acesso à sua câmera para:' },
    'consent.camera.item1': { en: 'Capture ASL signs in real time.', pt: 'Capturar gestos de Libras em tempo real.' },
    'consent.camera.item2': { en: 'Recognize signs and convert them to text for other participants.', pt: 'Reconhecer sinais e convertê-los em texto para os demais participantes.' },
    'consent.camera.btn': { en: 'Allow Camera', pt: 'Permitir Câmera' },
    'consent.camera.btnAria': { en: 'Allow camera access', pt: 'Permitir acesso à câmera' },
    'consent.mic.title': { en: 'Microphone Permission', pt: 'Permissão de Microfone' },
    'consent.mic.desc': { en: 'AccessMesh AI needs microphone access to:', pt: 'A AccessMesh-AI precisa de acesso ao seu microfone para:' },
    'consent.mic.item1': { en: 'Transcribe your speech in real time.', pt: 'Transcrever sua fala em tempo real.' },
    'consent.mic.item2': { en: 'Adapt audio for captions and accessibility.', pt: 'Adaptar o áudio para legendas e acessibilidade.' },
    'consent.mic.btn': { en: 'Allow Microphone', pt: 'Permitir Microfone' },
    'consent.mic.btnAria': { en: 'Allow microphone access', pt: 'Permitir acesso ao microfone' },
    'consent.decline': { en: 'Decline', pt: 'Recusar' },
    'consent.declineAria': { en: 'Decline and go back', pt: 'Recusar e voltar' },
    'consent.privacy': { en: '🔒 Audio and video are processed locally and via Microsoft Azure. No data is recorded or shared with third parties.', pt: '🔒 Áudio e vídeo são processados localmente e via Microsoft Azure. Nenhum dado é gravado ou compartilhado com terceiros.' },
    'consent.aiWarning.prefix': { en: '🤖 AI in use:', pt: '🤖 IA em uso:' },
    'consent.aiWarning.text': { en: ' Transcription, translation and accessibility are processed by AI models (Azure OpenAI / Azure Speech). Results may contain errors — review critical information before using it.', pt: ' Transcrição, tradução e acessibilidade são processadas por modelos de IA (Azure OpenAI / Azure Speech). Os resultados podem conter erros — revise informações críticas antes de utilizá-las.' },

    // AI transparency banner
    'aiBanner.ariaLabel': { en: 'AI usage notice', pt: 'Aviso de IA em uso' },
    'aiBanner.title': { en: 'AI in use', pt: 'IA em uso' },
    'aiBanner.text': { en: 'Transcription, translation and accessibility are generated by AI and may contain errors.', pt: 'Transcrição, tradução e acessibilidade são geradas por IA e podem conter erros.' },
    'aiBanner.learnMore': { en: 'Learn more', pt: 'Saiba mais' },
    'aiBanner.learnMoreAria': { en: 'Learn more about AI usage (opens in new tab)', pt: 'Saiba mais sobre o uso de IA (abre em nova aba)' },

    // --- Transcript panel ---
    'transcript.title': { en: 'Live Transcript', pt: 'Transcrição ao Vivo' },
    'transcript.empty': {
        en: 'Captions will appear here during the meeting.',
        pt: 'As legendas aparecerão aqui durante a reunião.',
    },
    'transcript.you': { en: 'You', pt: 'Você' },
    'transcript.line': { en: 'line', pt: 'linha' },
    'transcript.lines': { en: 'lines', pt: 'linhas' },
    'transcript.confidence': { en: 'Confidence', pt: 'Confiança' },

    // --- Chat panel ---
    'chat.title': { en: 'Meeting Chat', pt: 'Chat da Reunião' },
    'chat.you': { en: 'You', pt: 'Você' },
    'chat.placeholder': { en: 'Type a message…', pt: 'Digite uma mensagem…' },
    'chat.send': { en: 'Send message', pt: 'Enviar mensagem' },
    'chat.empty': {
        en: 'No messages yet. Start the conversation!',
        pt: 'Nenhuma mensagem ainda. Comece a conversa!',
    },

    // --- Meeting controls ---
    'controls.mic': { en: 'Microphone', pt: 'Microfone' },
    'controls.micOn': { en: 'Mute microphone', pt: 'Silenciar microfone' },
    'controls.micOff': { en: 'Unmute microphone', pt: 'Ativar microfone' },
    'controls.camera': { en: 'Camera', pt: 'Câmera' },
    'controls.cameraOn': { en: 'Turn off camera', pt: 'Desligar câmera' },
    'controls.cameraOff': { en: 'Turn on camera', pt: 'Ligar câmera' },
    'controls.transcript': { en: 'Toggle transcript', pt: 'Alternar transcrição' },
    'controls.chat': { en: 'Toggle chat', pt: 'Alternar chat' },
    'controls.summary': { en: 'Meeting summary', pt: 'Resumo da reunião' },
    'controls.leave': { en: 'Leave meeting', pt: 'Sair da reunião' },
    'controls.settings': { en: 'Settings', pt: 'Configurações' },

    // --- Microphone input ---
    'mic.startRecording': { en: 'Start recording', pt: 'Iniciar gravação' },
    'mic.stopRecording': { en: 'Stop recording', pt: 'Parar gravação' },
    'mic.recording': { en: 'Recording…', pt: 'Gravando…' },

    // --- Gesture camera ---
    'gesture.title': { en: 'Sign Camera', pt: 'Câmera de Sinais' },
    'gesture.waiting': {
        en: 'Waiting for gesture recognition…',
        pt: 'Aguardando reconhecimento de gesto…',
    },
    'gesture.detected': { en: 'Detected: ', pt: 'Detectado: ' },
    'gesture.error': {
        en: 'Unable to start camera. Check permissions.',
        pt: 'Não foi possível iniciar a câmera. Verifique as permissões.',
    },
    'gesture.errorBoundary': {
        en: 'Camera component failed to load.',
        pt: 'O componente de câmera falhou ao carregar.',
    },

    // --- Summary modal ---
    'summary.title': { en: 'Meeting Summary', pt: 'Resumo da Reunião' },
    'summary.loading': { en: 'Generating summary…', pt: 'Gerando resumo…' },
    'summary.error': {
        en: 'Unable to generate summary.',
        pt: 'Não foi possível gerar o resumo.',
    },
    'summary.close': { en: 'Close', pt: 'Fechar' },
    'summary.copy': { en: 'Copy summary', pt: 'Copiar resumo' },
    'summary.copied': { en: 'Copied!', pt: 'Copiado!' },
    'summary.participants': { en: 'Participants', pt: 'Participantes' },
    'summary.duration': { en: 'Duration', pt: 'Duração' },
    'summary.keyPoints': { en: 'Key Points', pt: 'Pontos Principais' },
    'summary.noContent': {
        en: 'No summary content available.',
        pt: 'Nenhum conteúdo de resumo disponível.',
    },
    'summary.genTitle': { en: 'Generate Meeting Minutes', pt: 'Gerar Ata da Reunião' },
    'summary.prompt': {
        en: 'Click <strong>Generate</strong> to create a summary with the key points from all messages in this session.',
        pt: 'Clique em <strong>Gerar</strong> para criar um resumo com os pontos-chave de todas as mensagens desta sessão.',
    },
    'summary.analyzing': { en: 'Analyzing transcriptions…', pt: 'Analisando transcrições…' },
    'summary.stub': {
        en: 'Stub mode — configure AZURE_OPENAI_KEY for AI summary.',
        pt: 'Modo stub — configure AZURE_OPENAI_KEY para sumário com IA.',
    },
    'summary.section': { en: 'Summary', pt: 'Resumo' },
    'summary.analyzed': {
        en: '{count} message(s) analyzed · session {id}',
        pt: '{count} mensagem(s) analisadas · sessão {id}',
    },
    'summary.generate': { en: 'Generate', pt: 'Gerar' },
    'summary.regenerate': { en: 'Regenerate', pt: 'Regenerar' },

    // Additional transcript keys
    'transcript.ariaLabel': { en: 'Live meeting transcript', pt: 'Transcrição ao vivo da reunião' },
    'transcript.confidenceAria': { en: 'Transcription confidence {pct}%', pt: 'Confiança da transcrição {pct}%' },
    'transcript.confidenceTitle': { en: 'STT confidence: {pct}%', pt: 'Confiança STT: {pct}%' },

    // Additional meeting controls keys
    'controls.stopRecording': { en: 'Stop recording', pt: 'Parar gravação' },
    'controls.mute': { en: 'Mute', pt: 'Silenciar' },
    'controls.unmute': { en: 'Unmute', pt: 'Tirar do mudo' },
    'controls.stopCamera': { en: 'Stop camera', pt: 'Desligar câmera' },
    'controls.startCamera': { en: 'Start camera', pt: 'Ligar câmera' },
    'controls.stopScreen': { en: 'Stop sharing', pt: 'Parar compartilhamento' },
    'controls.shareScreen': { en: 'Share screen', pt: 'Compartilhar tela' },
    'controls.hideCaptions': { en: 'Hide captions', pt: 'Ocultar legendas' },
    'controls.showCaptions': { en: 'Show captions', pt: 'Mostrar legendas' },
    'controls.leaveMeeting': { en: 'Leave meeting', pt: 'Sair da reunião' },

    // Additional gesture camera keys
    'gesture.loadingAI': { en: 'Loading AI…', pt: 'Carregando IA…' },
    'gesture.hand': { en: 'hand', pt: 'mão' },
    'gesture.hands': { en: 'hands', pt: 'mãos' },
    'gesture.local': { en: 'Processed locally', pt: 'Processado localmente' },
    'gesture.localAria': {
        en: 'Landmarks are processed locally in your browser via MediaPipe. Only gesture vectors (not video frames) are sent to the server.',
        pt: 'Marcos são processados localmente no seu navegador via MediaPipe. Apenas vetores de gestos (não frames de vídeo) são enviados ao servidor.',
    },
    'gesture.stopCamera': { en: 'Stop camera', pt: 'Desligar câmera' },
    'gesture.startCamera': { en: 'Start gesture camera', pt: 'Iniciar câmera de gestos' },
    'gesture.loading': { en: 'Loading', pt: 'Carregando' },
    'gesture.useAI': { en: 'Use AI for complex signs', pt: 'Usar IA para sinais complexos' },
    'gesture.accessDenied': {
        en: 'Camera access denied — check browser permissions.',
        pt: 'Acesso à câmera negado — verifique as permissões do navegador.',
    },
    'gesture.cameraOff': { en: 'Camera off', pt: 'Câmera desligada' },
    'gesture.unavailable': { en: 'Gesture camera unavailable', pt: 'Câmera de gestos indisponível' },
    'gesture.retry': { en: 'Retry', pt: 'Tentar novamente' },

    // Additional mic keys
    'mic.error': { en: 'Error — try again', pt: 'Erro — tente novamente' },
    'mic.startVoice': { en: 'Start voice input', pt: 'Iniciar entrada de voz' },

    // --- Error boundary ---
    'errorBoundary.title': { en: 'Something went wrong', pt: 'Algo deu errado' },
    'errorBoundary.generic': { en: 'An unexpected error occurred.', pt: 'Ocorreu um erro inesperado.' },
    'errorBoundary.retry': { en: 'Try Again', pt: 'Tentar Novamente' },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns the active locale code ('en' or 'pt'). */
export function getLang(): 'en' | 'pt' {
    const raw =
        localStorage.getItem('preferredLanguage') ??
        sessionStorage.getItem('language') ??
        'en-US';
    return raw.startsWith('pt') ? 'pt' : 'en';
}

/** Translates a key – falls back to the English string, then the key itself. */
export function translate(key: string): string {
    const entry = translations[key];
    if (!entry) return key;
    const lang = getLang();
    return entry[lang] ?? entry['en'] ?? key;
}

/** Broadcasts a DOM event so all `useTranslation` consumers re-render. */
export function notifyLanguageChange(): void {
    window.dispatchEvent(new Event('accessmesh:languagechange'));
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Returns a `t(key)` function that re-renders automatically whenever the
 * user changes language (via `notifyLanguageChange()`).
 *
 * @example
 * const { t } = useTranslation();
 * return <button>{t('controls.leave')}</button>;
 */
export function useTranslation() {
    const [, forceRender] = useState(0);

    useEffect(() => {
        const handler = () => forceRender((n) => n + 1);
        window.addEventListener('accessmesh:languagechange', handler);
        return () => window.removeEventListener('accessmesh:languagechange', handler);
    }, []);

    return { t: translate };
}

export default useTranslation;
