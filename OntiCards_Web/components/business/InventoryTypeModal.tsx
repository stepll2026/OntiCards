'use client';

import React, { useState, useEffect } from 'react';
import { Modal, Button } from 'antd';
import { 
  Search, 
  Aperture, 
  Info,
  ArrowRight,
  CheckCircle
} from 'lucide-react';

export type InventoryType = 'target' | 'global';

interface InventoryTypeModalProps {
  visible: boolean;
  onClose: () => void;
  onSelectType: (type: InventoryType) => void;
  currentDataSourceName: string;
}

// 检测是否为深色模式
const useDarkMode = () => {
  const [isDark, setIsDark] = useState(false);
  
  useEffect(() => {
    const checkDark = () => {
      // 项目使用 data-theme 属性，不是 dark 类名
      const dark = document.documentElement.getAttribute('data-theme') === 'dark';
      setIsDark(dark);
    };
    
    checkDark();
    
    // 监听主题变化
    const observer = new MutationObserver(checkDark);
    observer.observe(document.documentElement, { 
      attributes: true, 
      attributeFilter: ['data-theme'] 
    });
    
    return () => observer.disconnect();
  }, []);
  
  return isDark;
};

// 深色模式颜色
const getColors = (isDark: boolean) => isDark ? {
  text: '#f1f5f9',
  textSecondary: '#94a3b8',
  textMuted: '#64748b',
  border: '#334155',
  cardBg: '#1e293b',
  cardHoverBg: '#334155',
  infoBg: 'rgba(99, 102, 241, 0.1)',
  infoBorder: 'rgba(99, 102, 241, 0.3)',
  headerBg: '#1e293b',
  contentBg: '#1e293b',
} : {
  text: '#1e293b',
  textSecondary: '#64748b',
  textMuted: '#94a3b8',
  border: '#e2e8f0',
  cardBg: '#ffffff',
  cardHoverBg: '#ffffff',
  infoBg: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
  infoBorder: '#e2e8f0',
  headerBg: '#ffffff',
  contentBg: '#ffffff',
};

// 盘点类型说明
const INVENTORY_TYPE_INFO = {
  target: {
    title: '定向盘点',
    icon: Search,
    description: '针对特定表进行字段注释推荐和关系发现',
    features: [
      '指定目标表（需要推荐注释的表）',
      '指定参考表（提供标准注释的表）',
      '可选：上传字典文件辅助匹配',
      '生成字段注释推荐和表关系'
    ],
    gradient: 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)',
    bgGradient: 'linear-gradient(135deg, #eff6ff 0%, #e0e7ff 100%)',
    accentColor: '#3b82f6'
  },
  global: {
    title: '全域盘点',
    icon: Aperture,
    description: '自动发现数据源中所有表之间的关联关系',
    features: [
      '全量分析数据源中的所有表',
      '发现表与表之间的外键关系',
      '识别语义关联和值域关联',
      '生成关系图谱和JOIN建议',
      '支持多数据源跨源关系发现'
    ],
    gradient: 'linear-gradient(135deg, #a855f7 0%, #ec4899 100%)',
    bgGradient: 'linear-gradient(135deg, #faf5ff 0%, #fdf2f8 100%)',
    accentColor: '#a855f7'
  }
};

const InventoryTypeModal: React.FC<InventoryTypeModalProps> = ({
  visible,
  onClose,
  onSelectType,
  currentDataSourceName
}) => {
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);
  const isDark = useDarkMode();
  const colors = getColors(isDark);

  // 基础样式（不依赖运行时变量）
  const baseStyles = {
    container: {
      padding: '24px'
    },
    header: {
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      marginBottom: '20px'
    },
    headerIcon: {
      width: '48px',
      height: '48px',
      borderRadius: '14px',
      background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 4px 12px rgba(99, 102, 241, 0.4)'
    },
    headerText: {
      flex: 1
    },
    headerTitle: {
      fontSize: '20px',
      fontWeight: 600,
      color: colors.text,
      margin: 0,
      lineHeight: 1.4
    },
    headerSubtitle: {
      fontSize: '14px',
      color: colors.textSecondary,
      marginTop: '2px'
    },
    infoBox: {
      background: colors.infoBg,
      borderRadius: '12px',
      padding: '16px 16px 16px 12px',
      marginBottom: '24px',
      border: `1px solid ${colors.infoBorder}`
    },
    infoContent: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: '8px'
    },
    infoText: {
      fontSize: '14px',
      color: colors.textSecondary,
      lineHeight: 1.6,
      paddingLeft: '0'
    },
    cardsContainer: {
      display: 'grid',
      gridTemplateColumns: 'repeat(2, 1fr)',
      gap: '16px'
    },
    cardIcon: {
      width: '56px',
      height: '56px',
      borderRadius: '14px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: '16px',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
    },
    cardTitle: {
      fontSize: '18px',
      fontWeight: 600,
      color: colors.text,
      marginBottom: '8px',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    },
    badge: {
      fontSize: '11px',
      fontWeight: 500,
      padding: '2px 8px',
      borderRadius: '10px'
    },
    cardDesc: {
      fontSize: '14px',
      color: colors.textSecondary,
      marginBottom: '16px',
      lineHeight: 1.5
    },
    featureList: {
      listStyle: 'none',
      padding: 0,
      margin: 0,
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '10px',
      flex: 1
    },
    featureItem: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: '8px',
      fontSize: '13px',
      color: colors.textSecondary
    },
    featureDot: {
      width: '6px',
      height: '6px',
      borderRadius: '50%',
      marginTop: '6px',
      flexShrink: 0
    },
    cardButtonWrap: {
      marginTop: 'auto',
      paddingTop: '20px'
    },
    cardButton: {
      height: '40px',
      borderRadius: '10px',
      fontWeight: 500,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '6px',
      transition: 'all 0.2s ease',
      width: '100%'
    }
  };

  // 获取卡片样式（依赖 isHovered 运行时变量）
  const getCardStyle = (type: string) => {
    const isHovered = hoveredCard === type;
    return {
      position: 'relative' as const,
      background: isHovered ? colors.cardHoverBg : colors.cardBg,
      borderRadius: '16px',
      padding: '24px',
      cursor: 'pointer',
      transition: 'all 0.3s ease',
      border: `2px solid ${isHovered ? '#6366f1' : (isDark ? '#334155' : '#e2e8f0')}`,
      boxShadow: isHovered 
        ? (isDark ? '0 8px 24px rgba(0, 0, 0, 0.4)' : '0 8px 24px rgba(0, 0, 0, 0.12)')
        : (isDark ? '0 1px 3px rgba(0, 0, 0, 0.3)' : '0 1px 3px rgba(0, 0, 0, 0.08)'),
      transform: isHovered ? 'translateY(-2px)' : 'none',
      display: 'flex',
      flexDirection: 'column' as const,
      minHeight: '320px'
    };
  };

  return (
    <Modal
      open={visible}
      onCancel={onClose}
      footer={null}
      width={760}
      centered
      closable={false}
      styles={{
        body: { padding: '0', background: isDark ? '#1e293b' : '#ffffff' },
        content: { borderRadius: '16px', overflow: 'hidden', background: isDark ? '#1e293b' : '#ffffff' },
        header: { display: 'none' },
        mask: { background: isDark ? 'rgba(0, 0, 0, 0.7)' : 'rgba(0, 0, 0, 0.45)' }
      }}
    >
      {/* Header */}
      <div style={{ padding: '24px 24px 0 24px', background: 'transparent' }}>
        <div style={baseStyles.header}>
          <div style={baseStyles.headerIcon}>
            <Search size={24} color="#ffffff" />
          </div>
          <div style={baseStyles.headerText}>
            <h2 style={baseStyles.headerTitle}>选择盘点类型</h2>
            <p style={baseStyles.headerSubtitle}>当前数据源：{currentDataSourceName}</p>
          </div>
          <Button 
            type="text" 
            onClick={onClose}
            style={{ 
              width: '32px', 
              height: '32px', 
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: colors.textSecondary,
              background: 'transparent',
              border: 'none'
            }}
          >
            ✕
          </Button>
        </div>
      </div>

      <div style={baseStyles.container}>
        {/* 说明 */}
        <div style={baseStyles.infoBox}>
          <div style={baseStyles.infoContent}>
            <Info size={20} color={isDark ? '#818cf8' : '#6366f1'} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div style={{ ...baseStyles.infoText, paddingLeft: 0 }}>
              <p style={{ margin: '0 0 8px 0', fontWeight: 500, color: colors.text }}>请选择您想要执行的盘点类型：</p>
              <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', lineHeight: 1.8 }}>
                <li style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: isDark ? '#60a5fa' : '#3b82f6', marginTop: '8px', flexShrink: 0 }} />
                  <span><strong style={{ color: isDark ? '#60a5fa' : '#3b82f6' }}>定向盘点</strong>：针对特定表进行精细化的字段注释推荐和关系发现</span>
                </li>
                <li style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                  <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: isDark ? '#c084fc' : '#a855f7', marginTop: '8px', flexShrink: 0 }} />
                  <span><strong style={{ color: isDark ? '#c084fc' : '#a855f7' }}>全域盘点</strong>：对整个数据源进行全面扫描，自动发现所有表之间的关联关系</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* 卡片选择 */}
        <div style={baseStyles.cardsContainer}>
          {Object.entries(INVENTORY_TYPE_INFO).map(([type, info]) => {
            const Icon = info.icon;
            const isHovered = hoveredCard === type;
            
            return (
              <div
                key={type}
                style={getCardStyle(type)}
                onMouseEnter={() => setHoveredCard(type)}
                onMouseLeave={() => setHoveredCard(null)}
                onClick={() => onSelectType(type as InventoryType)}
              >
                {/* 卡片图标 */}
                <div style={{ 
                  ...baseStyles.cardIcon, 
                  background: info.gradient 
                }}>
                  <Icon size={28} color="#ffffff" />
                </div>

                {/* 标题 */}
                <h3 style={baseStyles.cardTitle}>
                  {info.title}
                  <span style={{ 
                    ...baseStyles.badge, 
                    background: isDark ? 'rgba(99, 102, 241, 0.2)' : info.bgGradient,
                    color: isDark ? '#a5b4fc' : info.accentColor
                  }}>
                    推荐
                  </span>
                </h3>

                {/* 描述 */}
                <p style={baseStyles.cardDesc}>
                  {info.description}
                </p>

                {/* 特性列表 */}
                <ul style={baseStyles.featureList}>
                  {info.features.map((feature, idx) => (
                    <li key={idx} style={baseStyles.featureItem}>
                      <div style={{ 
                        ...baseStyles.featureDot, 
                        background: info.accentColor 
                      }} />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                {/* 选择按钮 - 底部对齐 */}
                <div style={baseStyles.cardButtonWrap}>
                  <Button 
                    type="primary"
                    style={{ 
                      ...baseStyles.cardButton,
                      background: isHovered ? info.gradient : (isDark ? '#334155' : '#f1f5f9'),
                      border: 'none',
                      color: isHovered ? '#ffffff' : colors.textSecondary
                    }}
                    icon={isHovered ? <ArrowRight size={16} /> : <CheckCircle size={16} />}
                    iconPosition="end"
                  >
                    {isHovered ? '选择此类型' : '查看详情'}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Modal>
  );
};

export default InventoryTypeModal;
