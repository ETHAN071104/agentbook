import type { Config } from 'tailwindcss';

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        heading: ['Outfit', 'sans-serif'],
        body: ['Outfit', 'sans-serif'],
        display: ['Outfit', 'sans-serif'],
      },
      colors: {
        background: '#f0f7ff',
        foreground: '#1e293b',
        primary: {
          DEFAULT: '#2563eb',
          hover: '#1d4ed8',
          foreground: '#ffffff',
        },
        accent: {
          DEFAULT: '#3b82f6',
          foreground: '#ffffff',
        },
        clay: {
          white: '#ffffff',
          border: '#e2edf8',
          muted: '#64748b',
        },
        card: {
          DEFAULT: '#ffffff',
          foreground: '#1e293b',
        },
        royal: '#2563eb',
        'sky-glow': '#60a5fa',
        'purple-glow': '#a78bfa',
        success: '#22c55e',
        'indigo-deep': '#1e3a8a',
        dark: {
          bg: '#0f172a',
          card: '#1e293b',
          border: '#334155',
          text: '#f1f5f9',
          muted: '#94a3b8',
        },
      },
      borderRadius: {
        xl: '0.75rem',
        '2xl': '1rem',
      },
      boxShadow: {
        clay: '8px 8px 16px rgba(37, 99, 235, 0.07)',
        'clay-lg': '12px 12px 24px rgba(37, 99, 235, 0.10)',
        'clay-sm': '4px 4px 8px rgba(37, 99, 235, 0.05)',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'chart-draw': {
          '0%': { strokeDashoffset: '1000' },
          '100%': { strokeDashoffset: '0' },
        },
        'glow-pulse': {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '0.8' },
        },
        'gradient-drift': {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
      },
      animation: {
        float: 'float 3s ease-in-out infinite',
        'fade-in': 'fade-in 0.5s ease-out',
        'fade-in-up': 'fade-in-up 0.6s ease-out forwards',
        'chart-draw': 'chart-draw 2s ease-out forwards',
        'glow-pulse': 'glow-pulse 3s ease-in-out infinite',
        'gradient-drift': 'gradient-drift 8s ease infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
} satisfies Config;
