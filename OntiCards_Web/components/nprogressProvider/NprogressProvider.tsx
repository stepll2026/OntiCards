'use client'

import { AppProgressBar as ProgressBar } from 'next-nprogress-bar'
import type { ReactNode } from 'react'

const NprogressProvider = ({ children }: { children: ReactNode }) => {
  return (
    <>
      {children}
      <ProgressBar
        height="4px"
        color="#6366f1"
        options={{
          showSpinner: false,
          easing: 'ease-in-out',
          speed: 300,
          minimum: 0.1,
        }}
        disableSameURL={true}
        stopDelay={300}
      />
    </>
  )
}

export default NprogressProvider
