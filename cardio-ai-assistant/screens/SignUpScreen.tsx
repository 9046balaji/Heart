
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

const SignUpScreen: React.FC = () => {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  return (
    <div className="min-h-screen bg-[#111111] text-white flex flex-col items-center justify-center p-6 relative">
      <div className="w-16 h-16 bg-blue-900/30 rounded-2xl flex items-center justify-center mb-6 border border-blue-900/50">
        <span className="material-symbols-outlined text-blue-500 text-3xl">local_hospital</span>
      </div>

      <h1 className="text-3xl font-bold mb-2">Get Started</h1>
      <p className="text-slate-400 mb-8 text-center max-w-xs">Create an account to monitor your heart health.</p>

      <form onSubmit={(e) => { e.preventDefault(); navigate('/dashboard'); }} className="w-full max-w-sm space-y-4">
        <div className="relative">
            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">person</span>
            <input type="text" placeholder="Full Name" className="w-full h-14 bg-slate-800/30 border border-slate-700 rounded-xl pl-12 pr-4 outline-none focus:border-blue-500 transition-colors text-white placeholder:text-slate-500" />
        </div>
        
        <div className="relative">
            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">mail</span>
            <input type="email" placeholder="Email Address" className="w-full h-14 bg-slate-800/30 border border-slate-700 rounded-xl pl-12 pr-4 outline-none focus:border-blue-500 transition-colors text-white placeholder:text-slate-500" />
        </div>

        <div className="relative">
            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">phone</span>
            <input type="tel" placeholder="Mobile Number" className="w-full h-14 bg-slate-800/30 border border-slate-700 rounded-xl pl-12 pr-4 outline-none focus:border-blue-500 transition-colors text-white placeholder:text-slate-500" />
        </div>

        <div className="relative">
            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">lock</span>
            <input 
                type={showPassword ? "text" : "password"} 
                placeholder="Password" 
                className="w-full h-14 bg-slate-800/30 border border-slate-700 rounded-xl pl-12 pr-12 outline-none focus:border-blue-500 transition-colors text-white placeholder:text-slate-500" 
            />
            <span 
                className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 cursor-pointer hover:text-slate-300 transition-colors select-none"
                onClick={() => setShowPassword(!showPassword)}
            >
                {showPassword ? 'visibility' : 'visibility_off'}
            </span>
        </div>

        <div className="relative">
            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">lock_reset</span>
            <input 
                type={showConfirmPassword ? "text" : "password"} 
                placeholder="Confirm Password" 
                className="w-full h-14 bg-slate-800/30 border border-slate-700 rounded-xl pl-12 pr-12 outline-none focus:border-blue-500 transition-colors text-white placeholder:text-slate-500" 
            />
            <span 
                className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 cursor-pointer hover:text-slate-300 transition-colors select-none"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
            >
                {showConfirmPassword ? 'visibility' : 'visibility_off'}
            </span>
        </div>

        <button className="w-full h-14 bg-blue-500 hover:bg-blue-600 text-white font-bold rounded-xl mt-6 transition-all shadow-lg shadow-blue-500/30">
            Create Account
        </button>
      </form>

      <p className="text-center mt-6 text-slate-500 text-xs px-8">
        By creating an account, you agree to our <a href="#" className="text-blue-400">Terms of Service</a> and <a href="#" className="text-blue-400">Privacy Policy</a>.
      </p>

      <p className="text-center mt-8 text-slate-400 text-sm">
         Already have an account? <Link to="/login" className="text-blue-500 font-bold hover:underline">Log In</Link>
      </p>
    </div>
  );
};

export default SignUpScreen;
