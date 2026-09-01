'use client'

import React from 'react'

interface ActivityItemProps {
  icon?: React.ReactNode
  title: string
  description?: string
  time: string
  type?: 'success' | 'info' | 'warning' | 'error'
}

const ActivityItem: React.FC<ActivityItemProps> = ({
  icon,
  title,
  description,
  time,
  type = 'info'
}) => {
  const typeColors = {
    success: 'bg-green-100 text-green-600',
    info: 'bg-blue-100 text-blue-600',
    warning: 'bg-yellow-100 text-yellow-600',
    error: 'bg-red-100 text-red-600'
  }

  return (
    <div className="flex gap-4 py-4 border-b border-gray-100 last:border-0">
      <div className={`flex-shrink-0 w-10 h-10 rounded-full ${typeColors[type]} flex items-center justify-center`}>
        {icon || (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
          </svg>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">{title}</p>
        {description && (
          <p className="text-sm text-gray-500 mt-1">{description}</p>
        )}
        <p className="text-xs text-gray-400 mt-1">{time}</p>
      </div>
    </div>
  )
}

export default ActivityItem
