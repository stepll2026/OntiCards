'use client'

import React from 'react'

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description: string
  action?: {
    label: string
    onClick: () => void
  }
}

const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, description, action }) => {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4">
      {icon ? (
        <div 
          className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
          style={{ backgroundColor: 'rgba(var(--theme-primary), 0.1)' }}
        >
          <div style={{ color: 'rgb(var(--theme-primary))' }}>{icon}</div>
        </div>
      ) : (
        <div 
          className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
          style={{ backgroundColor: 'rgba(var(--theme-primary), 0.1)' }}
        >
          <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 20 20" style={{ color: 'rgb(var(--theme-primary))' }}>
            <path fillRule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clipRule="evenodd" />
          </svg>
        </div>
      )}
      <h3 className="text-lg font-semibold mb-2" style={{ color: 'rgb(var(--theme-text))' }}>{title}</h3>
      <p className="text-sm text-center max-w-md mb-6" style={{ color: 'rgb(var(--theme-text-secondary))' }}>{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="px-5 py-2.5 rounded-xl text-sm font-medium text-white transition-all"
          style={{ backgroundColor: 'rgb(var(--theme-primary))' }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgb(var(--theme-primary-hover))'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgb(var(--theme-primary))'
          }}
        >
          {action.label}
        </button>
      )}
    </div>
  )
}

export default EmptyState
