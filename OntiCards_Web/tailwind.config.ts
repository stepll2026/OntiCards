import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./pages/**/*.{js,ts,jsx,tsx,mdx}', './components/**/*.{js,ts,jsx,tsx,mdx}', './app/**/*.{js,ts,jsx,tsx,mdx}'],
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        primary: {
          25: '#F5F8FF',
          50: '#EBF5FF',
          100: '#E1EFFE',
          200: '#C3DDFD',
          300: '#A4CAFE',
          400: '#528BFF',
          500: '#2970FF',
          600: '#1C64F2',
          700: '#1A56DB',
        },
      },
      flex: {
        3: '3 3 0%',
        2: '2 2 0%',
      },
      corePlugins: {
        preflight: false,
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      },
      screens: {
        smb: '440px',
      },
      fontSize: {
        '12': '12px',
        '14': '14px',
        '20': '20px',
        '18': '18px',
        '16': '16px',
        '5xl': ['3.052rem', {}],
        '4xl': ['2.25rem', '2.8rem'],
        '3xl': ['1.875rem', '3.25rem'],
        '2xl': '1.5rem',
      },
      zIndex: {
        9999: '9999',
        999: '999',
        99: '99',
        9: '9',
      },
      fontWeight: {
        normal: 'normal',
      },
      width: {
        'calc-screen-52': 'calc(100vw - 17rem)',
        'calc-full-20': 'calc(100% - 20px)',
      },
      maxWidth: {
        'calc-screen-52': 'calc(100vw - 17rem)',
        'main': '800px',
      },
      boxShadow: {
        'red-xl': '0 0px 0px 2px rgba(239, 68, 68, 0.3)',
        'red-3xl': '0 0px 0px 8px rgba(239, 68, 68, 0.6)',
        '4': '0px 2px 4px 1px rgba(0,0,0,0.3)',
      },
    },
    fontFamily: {
      semiBold: ['Open Sans', 'Open Sans'],
    },
    borderRadius: {
      round: '50%',
    },
  },
  plugins: [],
}
export default config
