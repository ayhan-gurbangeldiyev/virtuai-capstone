import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Mail, Lock, User, ArrowRight, Loader2, Check, Zap, Shield, Rocket } from 'lucide-react';
import { toast } from 'sonner';
import { motion } from 'framer-motion';

const clashFont = "'Clash Display', 'Satoshi', system-ui, sans-serif";
const satoshiFont = "'Satoshi', 'Inter', system-ui, sans-serif";

const fadeUp = { hidden: { opacity: 0, y: 30 }, show: { opacity: 1, y: 0 } };
const fadeIn = { hidden: { opacity: 0 }, show: { opacity: 1 } };
const floatY = {
  animate: {
    y: [0, -14, 0],
    transition: { duration: 5, ease: 'easeInOut', repeat: Infinity },
  },
};
const scaleIn = {
  hidden: { opacity: 0, scale: 0.85 },
  show: { opacity: 1, scale: 1, transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] } },
};
const stagger = { show: { transition: { staggerChildren: 0.1 } } };

const features = [
  { icon: Zap, text: '6 platform, tek tık' },
  { icon: Shield, text: 'Verileriniz güvende' },
  { icon: Rocket, text: 'AI destekli içerik' },
];

export default function SignupPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const { signUp, signInWithGoogle, isConfigured } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isConfigured) {
      toast.error('Supabase henüz yapılandırılmamış');
      return;
    }
    if (!name || !email || !password) {
      toast.error('Lütfen tüm alanları doldurun');
      return;
    }
    if (password !== confirmPassword) {
      toast.error('Şifreler eşleşmiyor');
      return;
    }
    if (password.length < 6) {
      toast.error('Şifre en az 6 karakter olmalı');
      return;
    }
    setLoading(true);
    try {
      await signUp(email, password, name);
      setSuccess(true);
      toast.success('Hesabınız oluşturuldu! Email adresinizi kontrol edin.');
    } catch (error) {
      toast.error(error.message || 'Kayıt başarısız');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    if (!isConfigured) {
      toast.error('Supabase henüz yapılandırılmamış');
      return;
    }
    try {
      await signInWithGoogle();
    } catch (error) {
      toast.error(error.message || 'Google ile giriş başarısız');
    }
  };

  /* ── Success state ── */
  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white p-6" style={{ fontFamily: satoshiFont }}>
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center max-w-md"
        >
          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-emerald-400 to-green-500 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-green-500/25">
            <Check className="h-10 w-10 text-white" strokeWidth={3} />
          </div>
          <h2 className="text-3xl font-bold text-[#1a1a1a]" style={{ fontFamily: clashFont, fontWeight: 600 }}>
            Kayıt Başarılı! 🎉
          </h2>
          <p className="text-[#888] mt-3 text-[15px] leading-relaxed">
            Email adresinize bir doğrulama linki gönderdik.
            <br />Lütfen email'inizi kontrol edin.
          </p>
          <Link to="/login">
            <button className="mt-8 h-[48px] px-8 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-500 text-white text-[15px] font-semibold hover:shadow-lg hover:shadow-violet-500/25 transition-all active:scale-[0.98]">
              Giriş Sayfasına Git
            </button>
          </Link>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex" style={{ fontFamily: satoshiFont }}>
      {/* ═══════ LEFT PANEL ═══════ */}
      <div className="hidden lg:flex lg:w-[55%] relative overflow-hidden bg-[#0a0a0f]">
        {/* animated gradient orbs */}
        <div className="absolute inset-0">
          <motion.div
            animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
            transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute top-[20%] left-[30%] w-[500px] h-[500px] rounded-full"
            style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.4) 0%, transparent 70%)' }}
          />
          <motion.div
            animate={{ scale: [1.2, 1, 1.2], opacity: [0.25, 0.45, 0.25] }}
            transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
            className="absolute bottom-[15%] right-[20%] w-[400px] h-[400px] rounded-full"
            style={{ background: 'radial-gradient(circle, rgba(217,70,239,0.35) 0%, transparent 70%)' }}
          />
          <motion.div
            animate={{ scale: [1, 1.15, 1], opacity: [0.15, 0.3, 0.15] }}
            transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut', delay: 3 }}
            className="absolute top-[60%] left-[10%] w-[300px] h-[300px] rounded-full"
            style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.25) 0%, transparent 70%)' }}
          />
        </div>

        {/* grid overlay */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
            backgroundSize: '60px 60px',
          }}
        />

        {/* content */}
        <div className="relative z-10 flex flex-col items-center justify-center w-full px-12">
          <motion.div variants={scaleIn} initial="hidden" animate="show">
            <motion.div {...floatY} animate="animate">
              <div className="relative">
                <div
                  className="absolute inset-0 blur-[80px] opacity-60 rounded-full"
                  style={{
                    background: 'radial-gradient(circle, rgba(168,85,247,0.6) 0%, rgba(217,70,239,0.3) 50%, transparent 80%)',
                    transform: 'scale(1.3)',
                  }}
                />
                <img
                  src="/logo.png"
                  alt="Type Hype Mascot"
                  className="relative w-56 h-56 object-contain drop-shadow-2xl"
                  style={{ filter: 'drop-shadow(0 0 40px rgba(168,85,247,0.3))' }}
                />
              </div>
            </motion.div>
          </motion.div>

          <motion.div variants={stagger} initial="hidden" animate="show" className="text-center mt-8">
            <motion.h1
              variants={fadeUp}
              className="text-5xl font-bold text-white tracking-tight"
              style={{ fontFamily: clashFont, fontWeight: 600 }}
            >
              Type<span className="bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">Hype</span>
            </motion.h1>
            <motion.p variants={fadeUp} className="text-lg text-white/50 mt-3 max-w-xs mx-auto leading-relaxed">
              Sosyal medya içeriklerini
              <br />AI ile üret, farkını hisset.
            </motion.p>
            <motion.div variants={fadeUp} className="flex flex-wrap gap-3 justify-center mt-8">
              {features.map((f, i) => (
                <motion.div
                  key={i}
                  variants={fadeUp}
                  className="flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/5 backdrop-blur-sm"
                >
                  <f.icon className="w-3.5 h-3.5 text-violet-400" />
                  <span className="text-sm text-white/70">{f.text}</span>
                </motion.div>
              ))}
            </motion.div>
          </motion.div>

          <motion.div
            variants={fadeIn} initial="hidden" animate="show" transition={{ delay: 1 }}
            className="absolute bottom-8 left-0 right-0 text-center"
          >
            <p className="text-xs text-white/25">500+ içerik üreticisi Type Hype kullanıyor</p>
          </motion.div>
        </div>
      </div>

      {/* ═══════ RIGHT PANEL ═══════ */}
      <div className="w-full lg:w-[45%] flex items-center justify-center bg-white relative overflow-y-auto">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 via-fuchsia-500 to-violet-500" />

        <motion.div variants={stagger} initial="hidden" animate="show" className="w-full max-w-[400px] px-8 py-12">
          {/* mobile logo */}
          <motion.div variants={fadeUp} className="lg:hidden flex items-center justify-center gap-3 mb-10">
            <img src="/logo.png" alt="Type Hype" className="w-12 h-12 object-contain" />
            <span className="text-2xl font-bold text-[#1a1a1a]" style={{ fontFamily: clashFont, fontWeight: 600 }}>
              Type<span className="bg-gradient-to-r from-violet-600 to-fuchsia-500 bg-clip-text text-transparent">Hype</span>
            </span>
          </motion.div>

          {/* heading */}
          <motion.div variants={fadeUp}>
            <h2 className="text-3xl font-bold text-[#1a1a1a]" style={{ fontFamily: clashFont, fontWeight: 600 }}>
              Hesap Oluştur ✨
            </h2>
            <p className="text-[#888] mt-2 text-[15px]">Ücretsiz başla, hemen içerik üretmeye başla</p>
          </motion.div>

          {/* Google button */}
          <motion.div variants={fadeUp} className="mt-7">
            <button
              onClick={handleGoogleSignIn}
              className="w-full h-[52px] flex items-center justify-center gap-3 rounded-2xl border-2 border-[#eee] bg-white hover:bg-[#fafafa] hover:border-[#ddd] transition-all duration-200 active:scale-[0.98]"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              <span className="text-[15px] font-semibold text-[#333]">Google ile Kayıt Ol</span>
            </button>
          </motion.div>

          {/* divider */}
          <motion.div variants={fadeUp} className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[#eee]" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-white px-4 text-xs uppercase tracking-widest text-[#bbb]">veya</span>
            </div>
          </motion.div>

          {/* form */}
          <motion.form variants={fadeUp} onSubmit={handleSubmit} className="space-y-3">
            <div className="relative">
              <User className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#ccc]" />
              <input
                type="text"
                placeholder="Adınız Soyadınız"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full h-[48px] pl-11 pr-4 rounded-xl border-2 border-[#f0f0f0] bg-[#fafafa] text-sm text-[#333] placeholder:text-[#bbb] outline-none focus:border-violet-400 focus:bg-white transition-all"
                style={{ fontFamily: satoshiFont }}
                data-testid="signup-name"
              />
            </div>
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#ccc]" />
              <input
                type="email"
                placeholder="ornek@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full h-[48px] pl-11 pr-4 rounded-xl border-2 border-[#f0f0f0] bg-[#fafafa] text-sm text-[#333] placeholder:text-[#bbb] outline-none focus:border-violet-400 focus:bg-white transition-all"
                style={{ fontFamily: satoshiFont }}
                data-testid="signup-email"
              />
            </div>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#ccc]" />
              <input
                type="password"
                placeholder="En az 6 karakter"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full h-[48px] pl-11 pr-4 rounded-xl border-2 border-[#f0f0f0] bg-[#fafafa] text-sm text-[#333] placeholder:text-[#bbb] outline-none focus:border-violet-400 focus:bg-white transition-all"
                style={{ fontFamily: satoshiFont }}
                data-testid="signup-password"
              />
            </div>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#ccc]" />
              <input
                type="password"
                placeholder="Şifrenizi tekrar girin"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full h-[48px] pl-11 pr-4 rounded-xl border-2 border-[#f0f0f0] bg-[#fafafa] text-sm text-[#333] placeholder:text-[#bbb] outline-none focus:border-violet-400 focus:bg-white transition-all"
                style={{ fontFamily: satoshiFont }}
                data-testid="signup-confirm-password"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full h-[48px] rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-500 text-white text-[15px] font-semibold flex items-center justify-center gap-2 hover:shadow-lg hover:shadow-violet-500/25 transition-all active:scale-[0.98] disabled:opacity-60"
              style={{ fontFamily: satoshiFont }}
              data-testid="signup-submit"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
              {loading ? 'Hesap oluşturuluyor...' : 'Hesap Oluştur'}
            </button>
          </motion.form>

          {/* bottom link */}
          <motion.p variants={fadeUp} className="text-center text-sm text-[#999] mt-7">
            Zaten hesabın var mı?{' '}
            <Link to="/login" className="text-violet-600 hover:text-violet-700 font-semibold transition-colors">
              Giriş yap
            </Link>
          </motion.p>

          <motion.p
            variants={fadeIn} initial="hidden" animate="show" transition={{ delay: 0.8 }}
            className="text-center text-[11px] text-[#ccc] mt-6 leading-relaxed"
          >
            Kayıt olarak{' '}
            <span className="text-[#aaa] hover:text-violet-500 cursor-pointer transition-colors">Kullanım Koşulları</span>
            'nı ve{' '}
            <span className="text-[#aaa] hover:text-violet-500 cursor-pointer transition-colors">Gizlilik Politikası</span>
            'nı kabul etmiş olursunuz.
          </motion.p>
        </motion.div>
      </div>
    </div>
  );
}
