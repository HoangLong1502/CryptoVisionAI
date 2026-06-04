module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './hooks/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          500: '#f59e0b',
          900: '#78350f',
        },
      },
      keyframes: {
        priceFlashUp: {
          '0%': {
            backgroundColor: 'rgba(16, 185, 129, 0.85)',
            color: '#ecfdf5',
            boxShadow: '0 0 0 2px rgba(16, 185, 129, 0.9), 0 0 28px rgba(16, 185, 129, 0.75)',
            transform: 'scale(1.06)',
          },
          '45%': {
            backgroundColor: 'rgba(16, 185, 129, 0.35)',
            boxShadow: '0 0 0 1px rgba(16, 185, 129, 0.5), 0 0 12px rgba(16, 185, 129, 0.35)',
            transform: 'scale(1.02)',
          },
          '100%': {
            backgroundColor: 'transparent',
            color: 'inherit',
            boxShadow: 'none',
            transform: 'scale(1)',
          },
        },
        priceFlashDown: {
          '0%': {
            backgroundColor: 'rgba(244, 63, 94, 0.85)',
            color: '#fff1f2',
            boxShadow: '0 0 0 2px rgba(244, 63, 94, 0.9), 0 0 28px rgba(244, 63, 94, 0.75)',
            transform: 'scale(1.06)',
          },
          '45%': {
            backgroundColor: 'rgba(244, 63, 94, 0.35)',
            boxShadow: '0 0 0 1px rgba(244, 63, 94, 0.5), 0 0 12px rgba(244, 63, 94, 0.35)',
            transform: 'scale(1.02)',
          },
          '100%': {
            backgroundColor: 'transparent',
            color: 'inherit',
            boxShadow: 'none',
            transform: 'scale(1)',
          },
        },
      },
      animation: {
        'price-flash-up': 'priceFlashUp 0.75s ease-out',
        'price-flash-down': 'priceFlashDown 0.75s ease-out',
      },
    },
  },
  plugins: [],
};
