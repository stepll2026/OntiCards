'use client'

import React from 'react'

interface StatCardProps {
  title: string
  value: string | number
  icon?: React.ReactNode
  iconBg?: string
  iconColor?: string
  trend?: {
    value: string
    isPositive: boolean
  }
  description?: string
}

const StatCard: React.FC<StatCardProps> = ({ 
  title, 
  value, 
  icon, 
  iconBg = 'rgba(var(--theme-primary), 0.1)',
  iconColor = 'rgb(var(--theme-primary))',
  trend, 
  description 
}) => {
  return (
    <div 
      className="p-5 rounded-2xl border transition-all duration-200"
      style={{ 
        backgroundColor: 'rgb(var(--theme-bg))',
        borderColor: 'rgb(var(--theme-border))',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.05)'
        e.currentTarget.style.borderColor = 'rgba(var(--theme-primary), 0.3)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = 'none'
        e.currentTarget.style.borderColor = 'rgb(var(--theme-border))'
      }}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium" style={{ color: 'rgb(var(--theme-text-secondary))' }}>{title}</p>
          <p className="text-3xl font-bold mt-1" style={{ color: 'rgb(var(--theme-text))' }}>{value}</p>
          {description && (
            <p className="text-xs mt-1" style={{ color: 'rgb(var(--theme-text-muted))' }}>{description}</p>
          )}
          {trend && (
            <div 
              className={`inline-flex items-center gap-1 text-xs mt-2 px-2 py-0.5 rounded-full`}
              style={{ 
                backgroundColor: trend.isPositive ? 'rgba(82, 196, 26, 0.1)' : 'rgba(245, 34, 45, 0.1)',
                color: trend.isPositive ? '#52c41a' : '#f5222d'
              }}
            >
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                {trend.isPositive ? (
                  <path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
                ) : (
                  <path fillRule="evenodd" d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L9 12.586V5a1 1 0 012 0v7.586l2.293-2.293a1 1 0 011.414 0z" clipRule="evenodd" />
                )}
              </svg>
              <span>{trend.value}</span>
            </div>
          )}
        </div>
        {icon && (
          <div 
            className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: iconBg }}
          >
            <div style={{ color: iconColor }}>{icon}</div>
          </div>
        )}
      </div>
    </div>
  )
}

export default StatCard
