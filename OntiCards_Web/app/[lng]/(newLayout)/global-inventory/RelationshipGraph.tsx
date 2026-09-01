'use client'

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import * as d3 from 'd3'
import type { GraphNode, GraphEdge, RelationshipCardItem } from '@/api/globalInventory'

// ============ 常量配置 ============
const RELATIONSHIP_TYPE_LABELS: Record<string, { label: string; color: string; description: string }> = {
  'FK': { label: '外键', color: '#52c41a', description: '基于数据库外键约束发现的关系' },
  'Semantic': { label: '语义', color: '#722ed1', description: '基于字段语义相似性发现的关系' },
  'Value': { label: '值域', color: '#1890ff', description: '基于字段值域匹配发现的关系' },
  'foreign_key': { label: '外键', color: '#52c41a', description: '基于数据库外键约束发现的关系' },
  'semantic': { label: '语义', color: '#722ed1', description: '基于字段语义相似性发现的关系' },
  'same_name': { label: '同名', color: '#1890ff', description: '基于字段名称相同发现的关系' },
  'value_overlap': { label: '值域重叠', color: '#faad14', description: '基于字段值域重叠发现的关系' },
  'shared_field': { label: '共享字段', color: '#fa8c16', description: '基于共享字段发现的关系' }
}

const CARDINALITY_LABELS: Record<string, string> = {
  'one_to_one': '1:1',
  'one_to_many': '1:N',
  'many_to_one': 'N:1',
  'many_to_many': 'N:N'
}

const NODE_COLORS = {
  default: '#1890ff',
  high: '#52c41a',
  medium: '#faad14',
  low: '#8c8c8c'
}

const EDGE_COLORS = {
  high: '#52c41a',
  medium: '#faad14',
  low: '#8c8c8c',
  cross: '#fa8c16'
}

const DATASOURCE_COLORS = [
  '#1890ff', '#52c41a', '#722ed1', '#fa8c16',
  '#eb2f96', '#13c2c2', '#faad14', '#2f54eb'
]

// 性能阈值
const PERF = {
  LOW: 50,
  MEDIUM: 150,
  HIGH: 500,
  VERY_HIGH: 1000
}

// ============ 类型定义 ============
interface SimNode extends GraphNode {
  x: number
  y: number
  fx?: number | null
  fy?: number | null
}

interface SimEdge {
  source: SimNode
  target: SimNode
  label: string
  strength: number
  cardinality: string
  is_cross_source?: boolean
  source_datasource_name?: string
  target_datasource_name?: string
  join_conditions?: Array<{
    local_field: string
    remote_field: string
    confidence: number
    mapping_type?: string
    relationship_type?: string
  }>
  join_sql?: string
  join_type?: string
  join_condition?: string
  use_cases?: string[]
  business_relation?: {
    from_entity?: string
    to_entity?: string
    relation_description?: string
    from_role?: string
    to_role?: string
  }
  fusion_suggestion?: {
    primary_table?: string
    secondary_table?: string
    aggregation_hint?: string
    fusion_strategy?: string
  }
  sourceCard?: RelationshipCardItem
  targetCard?: RelationshipCardItem
  relationship?: any
}

interface Transform {
  x: number
  y: number
  k: number
}

interface Props {
  data: { nodes: GraphNode[]; edges: GraphEdge[] } | null
  loading?: boolean
  datasourceNameMap?: Map<string, string>
  relationshipCards?: RelationshipCardItem[]
}

// ============ 主组件 ============
export default function RelationshipGraph({ data, datasourceNameMap, relationshipCards }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const simulationRef = useRef<d3.Simulation<SimNode, SimEdge> | null>(null)

  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })
  const [isDark, setIsDark] = useState(false)
  const [selectedEdge, setSelectedEdge] = useState<SimEdge | null>(null)
  const [isSimRunning, setIsSimRunning] = useState(false)
  const [nodeRadius, setNodeRadius] = useState(28)
  const [hoveredEdge, setHoveredEdge] = useState<SimEdge | null>(null)

  // 内部状态
  const nodesRef = useRef<SimNode[]>([])
  const edgesRef = useRef<SimEdge[]>([])
  const transformRef = useRef<Transform>({ x: 0, y: 0, k: 1 })
  const isDraggingRef = useRef<'node' | 'canvas' | null>(null)
  const dragStartRef = useRef({ x: 0, y: 0, tx: 0, ty: 0 })
  const draggedNodeRef = useRef<SimNode | null>(null)
  const hoveredEdgeRef = useRef<SimEdge | null>(null)
  const rafRef = useRef<number | null>(null)
  const hasDraggedRef = useRef(false)
  const dragDistanceRef = useRef(0)
  const relationshipCardsRef = useRef(relationshipCards)
  const renderRef = useRef<() => void>(() => {})
  const initialScaleRef = useRef(1)
  // 追踪是否正在进行节点拖动（用于防止拖动后误触发边选中）
  const isNodeDraggingRef = useRef(false)

  // 保持 relationshipCards 引用
  useEffect(() => {
    relationshipCardsRef.current = relationshipCards
  }, [relationshipCards])

  // 注册原生滚轮事件监听器，阻止页面滚动
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const wheelHandler = (e: WheelEvent) => {
      const rect = canvas.getBoundingClientRect()
      if (e.clientX >= rect.left && e.clientX <= rect.right &&
          e.clientY >= rect.top && e.clientY <= rect.bottom) {
        e.preventDefault()
      }
    }

    canvas.addEventListener('wheel', wheelHandler, { passive: false })
    return () => {
      canvas.removeEventListener('wheel', wheelHandler)
    }
  }, [])

  // 计算数据规模级别
  const dataScaleLevel = useMemo(() => {
    const nodeCount = data?.nodes.length || 0
    const edgeCount = data?.edges.length || 0
    if (nodeCount > PERF.HIGH || edgeCount > PERF.VERY_HIGH) return 'extreme'
    if (nodeCount > PERF.MEDIUM || edgeCount > PERF.HIGH) return 'high'
    if (nodeCount > PERF.LOW || edgeCount > PERF.MEDIUM) return 'medium'
    return 'low'
  }, [data])

  // 节点颜色映射
  const datasourceColorMap = useMemo(() => {
    if (!data) return new Map<string, string>()
    const uniqueDsIds = [...new Set(data.nodes.map(n => n.datasource_id).filter(Boolean))]
    const map = new Map<string, string>()
    uniqueDsIds.forEach((dsId, i) => {
      if (dsId) map.set(dsId, DATASOURCE_COLORS[i % DATASOURCE_COLORS.length])
    })
    return map
  }, [data])

  const hasMultipleDatasources = datasourceColorMap.size > 1

  // 计算自适应节点半径和布局参数
  const layoutConfig = useMemo(() => {
    const nodeCount = data?.nodes.length || 0
    const edgeCount = data?.edges.length || 0
    const totalElements = nodeCount + edgeCount

    // 根据数据规模调整节点大小
    let radius: number
    let nodeSpacing: number
    let chargeStrength: number
    let linkDistance: number
    let collisionRadius: number
    let edgeWidth: number
    let showLabels: boolean
    let showEdgeLabels: boolean
    let showArrows: boolean
    let showNodeLabels: boolean

    if (totalElements > 3000) {
      // 超大规模：极简渲染
      radius = 6
      nodeSpacing = 50
      chargeStrength = -100
      linkDistance = 80
      collisionRadius = 20
      edgeWidth = 0.5
      showLabels = false
      showEdgeLabels = false
      showArrows = false
      showNodeLabels = false
    } else if (totalElements > 1500) {
      // 大规模
      radius = 10
      nodeSpacing = 35
      chargeStrength = -150
      linkDistance = 100
      collisionRadius = 25
      edgeWidth = 0.8
      showLabels = true
      showEdgeLabels = false
      showArrows = true
      showNodeLabels = true
    } else if (totalElements > 500) {
      // 中等规模
      radius = 14
      nodeSpacing = 25
      chargeStrength = -200
      linkDistance = 120
      collisionRadius = 30
      edgeWidth = 1.2
      showLabels = true
      showEdgeLabels = false
      showArrows = true
      showNodeLabels = true
    } else if (totalElements > 100) {
      // 小规模
      radius = 18
      nodeSpacing = 20
      chargeStrength = -250
      linkDistance = 140
      collisionRadius = 35
      edgeWidth = 1.5
      showLabels = true
      showEdgeLabels = true
      showArrows = true
      showNodeLabels = true
    } else {
      // 正常规模
      radius = 24
      nodeSpacing = 15
      chargeStrength = -300
      linkDistance = 160
      collisionRadius = 40
      edgeWidth = 1.8
      showLabels = true
      showEdgeLabels = true
      showArrows = true
      showNodeLabels = true
    }

    // 计算初始缩放级别（让图谱适应画布）
    const estimatedWidth = nodeCount * nodeSpacing
    const estimatedHeight = nodeCount * nodeSpacing * 0.8
    const scaleX = dimensions.width / (estimatedWidth + 200)
    const scaleY = dimensions.height / (estimatedHeight + 200)
    const autoScale = Math.min(scaleX, scaleY, 1) * 0.85

    return {
      radius,
      nodeSpacing,
      chargeStrength,
      linkDistance,
      collisionRadius,
      edgeWidth,
      showLabels,
      showEdgeLabels,
      showArrows,
      showNodeLabels,
      autoScale: Math.max(0.15, Math.min(1, autoScale))
    }
  }, [data?.nodes.length, data?.edges.length, dimensions])

  // 更新节点半径状态
  useEffect(() => {
    setNodeRadius(layoutConfig.radius)
  }, [layoutConfig.radius])

  // 深色模式
  useEffect(() => {
    const checkDark = () => setIsDark(document.documentElement.getAttribute('data-theme') === 'dark')
    checkDark()
    const observer = new MutationObserver(checkDark)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  // 容器尺寸 - 完全重写，确保可靠获取
  useEffect(() => {
    let mounted = true
    let timeoutIds: NodeJS.Timeout[] = []

    const updateDimensions = () => {
      if (!mounted || !containerRef.current) return

      const container = containerRef.current
      const rect = container.getBoundingClientRect()

      // 获取实际渲染尺寸
      let width = rect.width
      let height = rect.height

      // 如果容器尺寸为0，使用视口尺寸作为后备
      if (width === 0 || height === 0) {
        width = window.innerWidth * 0.9
        height = window.innerHeight * 0.6
      }

      // 确保尺寸是合理的
      width = Math.max(width, 400)
      height = Math.max(height, 300)

      setDimensions({ width, height })

      // 更新 Canvas 尺寸
      if (canvasRef.current) {
        canvasRef.current.width = width
        canvasRef.current.height = height
      }
    }

    // 首次更新 - 等待 DOM 布局完成
    timeoutIds.push(setTimeout(() => {
      if (mounted) updateDimensions()
    }, 0))

    // 第二次更新 - 确保弹框动画完成
    timeoutIds.push(setTimeout(() => {
      if (mounted) updateDimensions()
    }, 100))

    // 第三次更新 - 作为最终保障
    timeoutIds.push(setTimeout(() => {
      if (mounted) updateDimensions()
    }, 300))

    // 设置 ResizeObserver 监听容器尺寸变化
    const ro = new ResizeObserver(() => {
      if (mounted) {
        requestAnimationFrame(updateDimensions)
      }
    })

    if (containerRef.current) {
      ro.observe(containerRef.current)
    }

    return () => {
      mounted = false
      timeoutIds.forEach(id => clearTimeout(id))
      ro.disconnect()
    }
  }, [])

  // 获取节点颜色
  const getNodeColor = useCallback((node: SimNode) => {
    if (hasMultipleDatasources && node.datasource_id) {
      return datasourceColorMap.get(node.datasource_id) || NODE_COLORS.default
    }
    if (node.related_count >= 5) return NODE_COLORS.high
    if (node.related_count >= 3) return NODE_COLORS.medium
    if (node.related_count >= 1) return NODE_COLORS.default
    return NODE_COLORS.low
  }, [hasMultipleDatasources, datasourceColorMap])

  // 获取边颜色
  const getEdgeColor = useCallback((edge: SimEdge) => {
    if (edge.is_cross_source) return EDGE_COLORS.cross
    if (edge.strength >= 0.85) return EDGE_COLORS.high
    if (edge.strength >= 0.7) return EDGE_COLORS.medium
    return EDGE_COLORS.low
  }, [])

  // 坐标转换：屏幕坐标 -> 图谱坐标
  const screenToGraph = useCallback((screenX: number, screenY: number) => {
    const { x: tx, y: ty, k } = transformRef.current
    const { width, height } = dimensions
    return {
      x: (screenX - width / 2 - tx) / k,
      y: (screenY - height / 2 - ty) / k
    }
  }, [dimensions])

  // ============ Canvas 渲染函数 ============
  const doRender = useCallback(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return

    const { width, height } = dimensions
    const { x: tx, y: ty, k } = transformRef.current
    const config = layoutConfig
    const r = config.radius * Math.max(0.3, Math.min(1.2, k))

    ctx.clearRect(0, 0, width, height)
    ctx.fillStyle = isDark ? '#1e293b' : '#f8fafc'
    ctx.fillRect(0, 0, width, height)

    ctx.save()
    ctx.translate(width / 2 + tx, height / 2 + ty)
    ctx.scale(k, k)

    const hovered = hoveredEdgeRef.current
    const selected = selectedEdge
    const nodes = nodesRef.current
    const edges = edgesRef.current

    // 超大规模时：只绘制悬停边和选中边
    if (dataScaleLevel === 'extreme') {
      // 绘制所有边（极简）
      edges.forEach(edge => {
        const sx = edge.source.x
        const sy = edge.source.y
        const tx2 = edge.target.x
        const ty2 = edge.target.y

        const dx = tx2 - sx
        const dy = ty2 - sy
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist === 0) return

        ctx.beginPath()
        ctx.moveTo(sx, sy)
        ctx.lineTo(tx2, ty2)
        ctx.strokeStyle = getEdgeColor(edge)
        ctx.lineWidth = 0.5
        ctx.globalAlpha = 0.3
        ctx.stroke()
        ctx.globalAlpha = 1
      })

      // 只高亮悬停/选中边
      if (hovered || selected) {
        const highlightEdge = hovered || selected
        const sx = highlightEdge.source.x
        const sy = highlightEdge.source.y
        const tx2 = highlightEdge.target.x
        const ty2 = highlightEdge.target.y

        ctx.beginPath()
        ctx.moveTo(sx, sy)
        ctx.lineTo(tx2, ty2)
        ctx.strokeStyle = getEdgeColor(highlightEdge)
        ctx.lineWidth = 2
        ctx.globalAlpha = 1
        ctx.stroke()
        ctx.globalAlpha = 1
      }

      // 绘制节点
      nodes.forEach(node => {
        const color = getNodeColor(node)
        ctx.beginPath()
        ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.globalAlpha = 0.8
        ctx.fill()
        ctx.globalAlpha = 1
      })

      ctx.restore()
      return
    }

    // 正常规模：完整渲染
    // 绘制边
    edges.forEach(edge => {
      const sx = edge.source.x
      const sy = edge.source.y
      const tx2 = edge.target.x
      const ty2 = edge.target.y

      const dx = tx2 - sx
      const dy = ty2 - sy
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist === 0) return

      const ux = dx / dist
      const uy = dy / dist
      const startX = sx + ux * r
      const startY = sy + uy * r
      const endX = tx2 - ux * r
      const endY = ty2 - uy * r

      const isHovered = hovered === edge
      const isSelected = selected === edge

      ctx.beginPath()
      ctx.moveTo(startX, startY)
      ctx.lineTo(endX, endY)
      ctx.strokeStyle = getEdgeColor(edge)
      ctx.lineWidth = isHovered ? config.edgeWidth * 2 : isSelected ? config.edgeWidth * 1.5 : config.edgeWidth
      ctx.globalAlpha = isHovered || isSelected ? 1 : 0.6

      if (edge.is_cross_source) {
        ctx.setLineDash([6, 4])
      } else {
        ctx.setLineDash([])
      }
      ctx.stroke()
      ctx.setLineDash([])

      // 箭头
      if (config.showArrows) {
        const arrowSize = Math.max(4, r * 0.4)
        const arrowAngle = Math.atan2(dy, dx)
        ctx.beginPath()
        ctx.moveTo(endX, endY)
        ctx.lineTo(
          endX - arrowSize * Math.cos(arrowAngle - Math.PI / 6),
          endY - arrowSize * Math.sin(arrowAngle - Math.PI / 6)
        )
        ctx.moveTo(endX, endY)
        ctx.lineTo(
          endX - arrowSize * Math.cos(arrowAngle + Math.PI / 6),
          endY - arrowSize * Math.sin(arrowAngle + Math.PI / 6)
        )
        ctx.stroke()
      }

      ctx.globalAlpha = 1

      // 边标签（仅小规模时显示）
      if (config.showEdgeLabels && nodes.length <= PERF.LOW && r >= 12) {
        const midX = (startX + endX) / 2
        const midY = (startY + endY) / 2
        const cardinality = CARDINALITY_LABELS[edge.cardinality] || ''
        const typeLabel = RELATIONSHIP_TYPE_LABELS[edge.label]?.label || ''
        const text = `${cardinality} ${typeLabel}`.trim()

        if (text) {
          ctx.font = 'bold 9px sans-serif'
          const metrics = ctx.measureText(text)
          const padding = 2
          const bgWidth = metrics.width + padding * 2
          const bgHeight = 12 + padding * 2

          ctx.fillStyle = getEdgeColor(edge)
          ctx.globalAlpha = 0.85
          ctx.beginPath()
          ctx.roundRect(midX - bgWidth / 2, midY - bgHeight / 2, bgWidth, bgHeight, 3)
          ctx.fill()

          ctx.fillStyle = '#fff'
          ctx.textAlign = 'center'
          ctx.textBaseline = 'middle'
          ctx.fillText(text, midX, midY)
          ctx.globalAlpha = 1
        }
      }
    })

    // 绘制节点
    nodes.forEach(node => {
      const color = getNodeColor(node)
      const tableName = node.label || node.id

      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2)

      const gradient = ctx.createRadialGradient(node.x - r * 0.3, node.y - r * 0.3, 0, node.x, node.y, r)
      gradient.addColorStop(0, lightenColor(color, 20))
      gradient.addColorStop(1, color)
      ctx.fillStyle = gradient
      ctx.fill()

      ctx.strokeStyle = 'rgba(255,255,255,0.4)'
      ctx.lineWidth = 1.5
      ctx.stroke()

      // 节点标签
      if (config.showNodeLabels) {
        const displayName = tableName.length > 6 ? tableName.substring(0, 5) + '..' : tableName
        const fontSize = Math.max(7, Math.min(10, r * 0.35))

        ctx.fillStyle = '#fff'
        ctx.font = `bold ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.shadowColor = 'rgba(0,0,0,0.3)'
        ctx.shadowBlur = 2
        ctx.fillText(displayName, node.x, node.y)
        ctx.shadowColor = 'transparent'
      }
    })

    ctx.restore()
  }, [dimensions, isDark, selectedEdge, layoutConfig, dataScaleLevel, getNodeColor, getEdgeColor])

  // 保存 render 函数引用
  useEffect(() => {
    renderRef.current = doRender
  }, [doRender])

  // 检测悬停边
  const detectHoveredEdge = useCallback((screenX: number, screenY: number) => {
    // 超大规模时使用采样检测
    if (dataScaleLevel === 'extreme') {
      return null // 性能考虑，极限规模时禁用边悬停检测
    }

    const graphPos = screenToGraph(screenX, screenY)
    // 使用固定的图谱坐标系半径，不随缩放变化
    // screenToGraph 已经处理了缩放变换
    const hitRadius = 15

    // 优先检测选中的边
    const selected = selectedEdge
    if (selected) {
      const dist = pointToLineDistance(
        graphPos.x, graphPos.y,
        selected.source.x, selected.source.y,
        selected.target.x, selected.target.y
      )
      if (dist < hitRadius) return selected
    }

    // 检测其他边
    for (const edge of edgesRef.current) {
      if (edge === selected) continue
      const dist = pointToLineDistance(
        graphPos.x, graphPos.y,
        edge.source.x, edge.source.y,
        edge.target.x, edge.target.y
      )
      if (dist < hitRadius) {
        return edge
      }
    }
    return null
  }, [screenToGraph, dataScaleLevel, selectedEdge])

  // 检测点击的节点
  const detectNode = useCallback((screenX: number, screenY: number) => {
    const graphPos = screenToGraph(screenX, screenY)
    // 增加节点检测半径，确保更容易点击到节点
    const hitRadius = Math.max(layoutConfig.radius * 2, 20)

    for (const node of nodesRef.current) {
      const dx = node.x - graphPos.x
      const dy = node.y - graphPos.y
      if (Math.sqrt(dx * dx + dy * dy) < hitRadius) {
        return node
      }
    }
    return null
  }, [screenToGraph, layoutConfig.radius])

  // 从卡片数据中查找边详情
  const findEdgeDetails = useCallback((sourceId: string, targetId: string): SimEdge | null => {
    const cards = relationshipCardsRef.current || []
    const sourceTableName = sourceId
    const targetTableName = targetId

    const sourceCard = cards.find(card => card.table_name === sourceTableName)
    const targetCard = cards.find(card => card.table_name === targetTableName)

    if (sourceCard?.card?.Relationships) {
      const relationship = sourceCard.card.Relationships.find(
        rel => rel.related_table === targetTableName
      )
      if (relationship) {
        return {
          source: nodesRef.current.find(n => n.id === sourceId)!,
          target: nodesRef.current.find(n => n.id === targetId)!,
          label: relationship.relationship_type === 'many_to_one' ? 'Semantic' :
                 relationship.relationship_type === 'one_to_many' ? 'Semantic' :
                 relationshipCards.find(c => c.table_name === targetTableName) ? 'Value' : 'Semantic',
          strength: relationship.confidence || 0,
          cardinality: relationship.relationship_type || 'many_to_one',
          is_cross_source: sourceCard.has_cross_source_relations,
          sourceCard,
          targetCard,
          relationship,
          join_conditions: relationship.join_fields?.map(f => ({
            local_field: f.local_field,
            remote_field: f.remote_field,
            confidence: f.confidence,
            mapping_type: (f as any).mapping_type,
            relationship_type: f.relationship_type
          })),
          join_type: relationship.join_suggestion?.join_type,
          join_condition: relationship.join_suggestion?.join_condition,
          join_sql: relationship.join_suggestion?.sample_sql,
          use_cases: relationship.join_suggestion?.use_cases,
          business_relation: relationship.business_relation,
          fusion_suggestion: relationship.fusion_suggestion
        }
      }
    }

    if (targetCard?.card?.Relationships) {
      const relationship = targetCard.card.Relationships.find(
        rel => rel.related_table === sourceTableName
      )
      if (relationship) {
        return {
          source: nodesRef.current.find(n => n.id === targetId)!,
          target: nodesRef.current.find(n => n.id === sourceId)!,
          label: relationship.relationship_type === 'many_to_one' ? 'Semantic' :
                 relationship.relationship_type === 'one_to_many' ? 'Semantic' : 'Semantic',
          strength: relationship.confidence || 0,
          cardinality: relationship.relationship_type || 'many_to_one',
          is_cross_source: targetCard.has_cross_source_relations,
          sourceCard: targetCard,
          targetCard: sourceCard,
          relationship,
          join_conditions: relationship.join_fields?.map(f => ({
            local_field: f.local_field,
            remote_field: f.remote_field,
            confidence: f.confidence,
            mapping_type: (f as any).mapping_type,
            relationship_type: f.relationship_type
          })),
          join_type: relationship.join_suggestion?.join_type,
          join_condition: relationship.join_suggestion?.join_condition,
          join_sql: relationship.join_suggestion?.sample_sql,
          use_cases: relationship.join_suggestion?.use_cases,
          business_relation: relationship.business_relation,
          fusion_suggestion: relationship.fusion_suggestion
        }
      }
    }

    return null
  }, [])

  // ============ 初始化模拟 ============
  useEffect(() => {
    if (!data?.nodes.length) return

    // 检查是否需要重新初始化（避免不必要的重置）
    const currentNodeCount = nodesRef.current.length
    const currentEdgeCount = edgesRef.current.length
    const newNodeCount = data.nodes.length
    const newEdgeCount = data.edges.length

    // 如果节点和边数量相同，且已有模拟运行中，则不重新初始化
    if (currentNodeCount === newNodeCount &&
        currentEdgeCount === newEdgeCount &&
        simulationRef.current &&
        !simulationRef.current.alpha()) {
      return
    }

    const { width, height } = dimensions
    const centerX = 0
    const centerY = 0

    if (simulationRef.current) {
      simulationRef.current.stop()
    }

    nodesRef.current = data.nodes.map((n, i) => {
      const angle = (2 * Math.PI * i) / data.nodes.length
      const radius = Math.min(width, height) * 0.35
      return {
        ...n,
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      }
    })

    const nodeMap = new Map(nodesRef.current.map(n => [n.id, n]))
    edgesRef.current = data.edges
      .map(e => {
        const source = nodeMap.get(e.source)
        const target = nodeMap.get(e.target)
        if (!source || !target) return null
        return {
          source,
          target,
          label: e.label,
          strength: e.strength,
          cardinality: e.cardinality,
          is_cross_source: e.is_cross_source,
          source_datasource_name: e.source_datasource_name,
          target_datasource_name: e.target_datasource_name,
          join_conditions: e.join_conditions,
          join_sql: e.join_sql,
          join_type: e.join_type,
          join_condition: e.join_condition,
          use_cases: e.use_cases,
          business_relation: e.business_relation,
          fusion_suggestion: e.fusion_suggestion
        }
      })
      .filter((e) => e !== null && e.source !== undefined && e.target !== undefined) as SimEdge[]

    hoveredEdgeRef.current = null
    setHoveredEdge(null)

    // 配置力模拟参数
    const config = layoutConfig
    const simulation = d3.forceSimulation<SimNode>(nodesRef.current)
      .force('link', d3.forceLink<SimNode, SimEdge>(edgesRef.current)
        .id(d => d.id)
        .distance(config.linkDistance)
        .strength(0.3))
      .force('charge', d3.forceManyBody().strength(config.chargeStrength))
      .force('center', d3.forceCenter(centerX, centerY))
      .force('collision', d3.forceCollide().radius(config.collisionRadius))

    // 大数据量时减少迭代
    if (dataScaleLevel === 'extreme') {
      simulation.alpha(0.3).alphaDecay(0.05)
    } else if (dataScaleLevel === 'high') {
      simulation.alpha(0.5).alphaDecay(0.03)
    } else {
      simulation.alphaDecay(0.02)
    }

    simulationRef.current = simulation
    setIsSimRunning(true)

    // 初始缩放
    initialScaleRef.current = config.autoScale
    transformRef.current = { x: 0, y: 0, k: config.autoScale }

    // 使用 ref 来渲染，避免闭包问题
    simulation.on('tick', () => {
      renderRef.current()
    })

    simulation.on('end', () => {
      setIsSimRunning(false)
      renderRef.current()
    })

    return () => {
      simulation.stop()
    }
  }, [data, dimensions, layoutConfig, dataScaleLevel])

  // ============ 鼠标交互 ============
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return

    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    hasDraggedRef.current = false
    isNodeDraggingRef.current = false
    const clickedNode = detectNode(x, y)

    if (clickedNode) {
      isDraggingRef.current = 'node'
      isNodeDraggingRef.current = true
      draggedNodeRef.current = clickedNode
      clickedNode.fx = clickedNode.x
      clickedNode.fy = clickedNode.y
      simulationRef.current?.alphaTarget(0.3).restart()
    } else {
      isDraggingRef.current = 'canvas'
      dragStartRef.current = {
        x,
        y,
        tx: transformRef.current.x,
        ty: transformRef.current.y
      }
    }
  }, [detectNode])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    if (isDraggingRef.current === 'node' && draggedNodeRef.current) {
      hasDraggedRef.current = true
      const pos = screenToGraph(x, y)
      draggedNodeRef.current.fx = pos.x
      draggedNodeRef.current.fy = pos.y
      simulationRef.current?.alpha(0.3).restart()
    } else if (isDraggingRef.current === 'canvas') {
      const dx = x - dragStartRef.current.x
      const dy = y - dragStartRef.current.y
      const distance = Math.sqrt(dx * dx + dy * dy)
      dragDistanceRef.current = distance

      // 只有移动超过5像素才算真正的拖动
      if (distance > 5) {
        hasDraggedRef.current = true
        transformRef.current = {
          ...transformRef.current,
          x: dragStartRef.current.tx + dx,
          y: dragStartRef.current.ty + dy
        }
        renderRef.current()
      }
    } else {
      // 边悬停检测（限制频率）
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      rafRef.current = requestAnimationFrame(() => {
        const hovered = detectHoveredEdge(x, y)
        if (hovered !== hoveredEdgeRef.current) {
          hoveredEdgeRef.current = hovered
          setHoveredEdge(hovered)
          renderRef.current()
        }
      })
    }
  }, [screenToGraph, detectHoveredEdge])

  const handleMouseUp = useCallback(() => {
    // 拖动结束后重置标志
    hasDraggedRef.current = false
    dragDistanceRef.current = 0

    if (isDraggingRef.current === 'node' && draggedNodeRef.current) {
      draggedNodeRef.current.fx = null
      draggedNodeRef.current.fy = null
      draggedNodeRef.current = null
      simulationRef.current?.alphaTarget(0)
    }
    isDraggingRef.current = null
  }, [])

  const handleClick = useCallback((e: React.MouseEvent) => {
    // 如果之前在拖动节点，跳过点击处理（避免误触发边选中）
    if (isNodeDraggingRef.current) {
      isNodeDraggingRef.current = false
      return
    }

    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    // 如果鼠标位置在节点范围内，不处理点击（这表示用户在拖动节点）
    if (detectNode(x, y)) return

    // 优先检测边
    const clickedEdge = detectHoveredEdge(x, y)
    if (clickedEdge) {
      const enhancedEdge = findEdgeDetails(clickedEdge.source.id, clickedEdge.target.id)
      const edgeToShow = enhancedEdge || clickedEdge

      if (selectedEdge &&
          selectedEdge.source === edgeToShow.source &&
          selectedEdge.target === edgeToShow.target) {
        setSelectedEdge(null)
      } else {
        setSelectedEdge(edgeToShow)
      }
      renderRef.current()
      return
    }

    // 点击空白区域，关闭详情面板
    if (selectedEdge) {
      setSelectedEdge(null)
      renderRef.current()
    }
  }, [detectNode, detectHoveredEdge, findEdgeDetails, selectedEdge])

  // 滚轮缩放
  const handleWheel = useCallback((e: React.WheelEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    const delta = e.deltaY > 0 ? 0.85 : 1.15
    const newK = Math.max(0.1, Math.min(4, transformRef.current.k * delta))

    const { x, y, k } = transformRef.current
    const graphX = (mouseX - rect.width / 2 - x) / k
    const graphY = (mouseY - rect.height / 2 - y) / k
    const newX = mouseX - rect.width / 2 - graphX * newK
    const newY = mouseY - rect.height / 2 - graphY * newK

    transformRef.current = { x: newX, y: newY, k: newK }
    renderRef.current()
  }, [])

  const handleDoubleClick = useCallback(() => {
    transformRef.current = { x: 0, y: 0, k: initialScaleRef.current }
    hoveredEdgeRef.current = null
    setHoveredEdge(null)
    renderRef.current()
  }, [])

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  // 空状态
  if (!data?.nodes.length) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400" style={{ minHeight: '400px' }}>
        <div className="text-center">
          <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
          <p>暂无关系图谱数据</p>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="relative w-full overflow-hidden"
      style={{ height: '100%', minHeight: '400px' }}
    >
      {/* 状态指示器 */}
      {isSimRunning && (
        <div style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          backgroundColor: '#3b82f6',
          color: 'white',
          fontSize: '12px',
          padding: '6px 14px',
          borderRadius: '20px',
          zIndex: 20,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          boxShadow: '0 4px 16px rgba(59, 130, 246, 0.4)'
        }}>
          <span style={{
            width: '8px',
            height: '8px',
            backgroundColor: 'white',
            borderRadius: '50%',
            animation: 'pulse 1.5s infinite'
          }}></span>
          布局计算中...
        </div>
      )}

      {/* 统计信息 */}
      <div style={{
        position: 'absolute',
        top: '16px',
        left: '16px',
        backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(12px)',
        borderRadius: '20px',
        padding: '12px 20px',
        zIndex: 10,
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1)',
        border: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`,
        fontSize: '13px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ color: '#1890ff' }}>
            <span style={{ fontWeight: 700, fontSize: '15px' }}>{data.nodes.length}</span> 节点
          </span>
          <span style={{ color: '#52c41a' }}>
            <span style={{ fontWeight: 700, fontSize: '15px' }}>{data.edges.length}</span> 边
          </span>
          {dataScaleLevel === 'extreme' && (
            <span style={{
              color: '#f97316',
              backgroundColor: 'rgba(249, 115, 22, 0.15)',
              padding: '2px 10px',
              borderRadius: '10px',
              fontSize: '11px',
              fontWeight: 500
            }} title="数据量大，部分功能已简化">
              ⚡ 简化模式
            </span>
          )}
        </div>
      </div>

      {/* 图例 */}
      <div style={{
        position: 'absolute',
        bottom: '16px',
        left: '16px',
        backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(12px)',
        borderRadius: '16px',
        padding: '14px 16px',
        zIndex: 10,
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1)',
        border: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`,
        maxWidth: '170px',
        fontSize: '12px'
      }}>
        <div style={{ fontWeight: 600, marginBottom: '10px', color: isDark ? '#e2e8f0' : '#374151' }}>图例</div>

        {!hasMultipleDatasources && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: NODE_COLORS.high }} />
              <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>≥5 关联</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: NODE_COLORS.medium }} />
              <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>3-4 关联</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: NODE_COLORS.default }} />
              <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>1-2 关联</span>
            </div>
            <div style={{ borderTop: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`, margin: '8px 0' }}></div>
          </>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
          <div style={{ width: '20px', height: '3px', backgroundColor: EDGE_COLORS.high, borderRadius: '2px' }} />
          <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>高置信 ≥85%</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
          <div style={{ width: '20px', height: '3px', backgroundColor: EDGE_COLORS.medium, borderRadius: '2px' }} />
          <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>中置信 70-85%</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
          <div style={{ width: '20px', height: '3px', backgroundColor: EDGE_COLORS.low, borderRadius: '2px' }} />
          <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>低置信 &lt;70%</span>
        </div>

        {data.edges.some(e => e.is_cross_source) && (
          <>
            <div style={{ borderTop: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`, margin: '8px 0' }}></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <svg width="20" height="8">
                <line x1="0" y1="4" x2="20" y2="4" stroke={EDGE_COLORS.cross} strokeWidth="1.5" strokeDasharray="4,2" />
              </svg>
              <span style={{ color: '#ea580c' }}>跨源关系</span>
            </div>
          </>
        )}
      </div>

      {/* 操作提示 */}
      <div style={{
        position: 'absolute',
        bottom: '16px',
        right: '16px',
        backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(12px)',
        borderRadius: '16px',
        padding: '12px 16px',
        zIndex: 10,
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1)',
        border: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`,
        fontSize: '12px'
      }}>
        <div style={{ color: isDark ? '#64748b' : '#9ca3af' }}>
          <div style={{ marginBottom: '4px' }}>拖拽空白区域移动画布</div>
          <div style={{ marginBottom: '4px' }}>滚轮缩放视图</div>
          <div style={{ marginBottom: '4px' }}>点击边查看详情</div>
          <div>双击重置视图</div>
        </div>
      </div>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        width={dimensions.width}
        height={dimensions.height}
        className="cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
        onWheel={handleWheel}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          touchAction: 'none'
        }}
      />

      {/* 详情面板 */}
      {selectedEdge && (
        <EdgeDetailPanel
          edge={selectedEdge}
          isDark={isDark}
          onClose={() => { setSelectedEdge(null); renderRef.current(); }}
        />
      )}
    </div>
  )
}

// ============ 详情面板组件 ============
interface EdgeDetailPanelProps {
  edge: SimEdge
  isDark: boolean
  onClose: () => void
}

function EdgeDetailPanel({ edge, isDark, onClose }: EdgeDetailPanelProps) {
  const getEdgeColor = (e: SimEdge) => {
    if (e.is_cross_source) return EDGE_COLORS.cross
    if (e.strength >= 0.85) return EDGE_COLORS.high
    if (e.strength >= 0.7) return EDGE_COLORS.medium
    return EDGE_COLORS.low
  }

  const sourceName = edge.source.label || edge.source.id
  const targetName = edge.target.label || edge.target.id

  // 通用圆角卡片样式
  const cardStyle: React.CSSProperties = {
    backgroundColor: isDark ? '#0f172a' : '#f8fafc',
    borderRadius: '12px',
    padding: '12px'
  }

  // 圆角标签样式
  const tagStyle: React.CSSProperties = {
    borderRadius: '6px',
    padding: '2px 8px'
  }

  return (
    <div
      className="w-[420px] max-h-[calc(100%-32px)] overflow-y-auto"
      style={{
        position: 'absolute',
        top: '16px',
        right: '16px',
        zIndex: 100,
        backgroundColor: isDark ? '#1e293b' : '#ffffff',
        border: `1px solid ${isDark ? '#334155' : '#e5e7eb'}`,
        borderRadius: '16px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
      }}
    >
      {/* 头部 */}
      <div
        className="sticky top-0 flex items-center justify-between z-10"
        style={{
          backgroundColor: isDark ? '#1e293b' : '#ffffff',
          padding: '16px 20px',
          borderBottom: `1px solid ${isDark ? '#334155' : '#e5e7eb'}`,
          borderRadius: '16px 16px 0 0'
        }}
      >
        <div className="font-medium flex items-center gap-2" style={{ color: isDark ? '#f1f5f9' : '#1f2937' }}>
          <span style={{ color: getEdgeColor(edge) }}>●</span>
          关系详情
          {edge.is_cross_source && (
            <span
              className="text-xs"
              style={{ backgroundColor: 'rgba(251, 146, 60, 0.2)', color: '#fa8c16', ...tagStyle }}
            >
              跨源
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded"
          style={{ color: isDark ? '#64748b' : '#9ca3af', backgroundColor: 'transparent', border: 'none', cursor: 'pointer' }}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div style={{ padding: '20px' }}>
        {/* 表名区域 */}
        <div
          className="flex items-center justify-between"
          style={{ ...cardStyle, marginBottom: '16px' }}
        >
          <div className="text-center flex-1">
            <div className="font-mono text-sm font-medium" style={{ color: '#3b82f6' }}>
              {sourceName}
            </div>
            {edge.source_datasource_name && (
              <div className="text-xs mt-1" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>
                {edge.source_datasource_name}
              </div>
            )}
            <div className="text-[10px] mt-1" style={{ color: isDark ? '#475569' : '#9ca3af' }}>源表</div>
          </div>

          <div className="flex flex-col items-center px-4">
            <div className="text-2xl font-bold" style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>
              {CARDINALITY_LABELS[edge.cardinality] || edge.cardinality || '—'}
            </div>
            <div className="text-[10px]" style={{ color: isDark ? '#475569' : '#9ca3af' }}>基数</div>
          </div>

          <div className="text-center flex-1">
            <div className="font-mono text-sm font-medium" style={{ color: '#22c55e' }}>
              {targetName}
            </div>
            {edge.target_datasource_name && (
              <div className="text-xs mt-1" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>
                {edge.target_datasource_name}
              </div>
            )}
            <div className="text-[10px] mt-1" style={{ color: isDark ? '#475569' : '#9ca3af' }}>目标表</div>
          </div>
        </div>

        {/* 属性信息 */}
        <div className="grid grid-cols-3 gap-2 text-xs" style={{ marginBottom: '16px' }}>
          <div className="flex flex-col text-center" style={{ ...cardStyle }}>
            <span className="mb-2" style={{ color: isDark ? '#64748b' : '#6b7280' }}>类型</span>
            <span
              className="text-white text-center"
              style={{ backgroundColor: RELATIONSHIP_TYPE_LABELS[edge.label]?.color || '#8c8c8c', ...tagStyle, fontWeight: 500 }}
            >
              {RELATIONSHIP_TYPE_LABELS[edge.label]?.label || edge.label || '未知'}
            </span>
          </div>
          <div className="flex flex-col text-center" style={{ ...cardStyle }}>
            <span className="mb-2" style={{ color: isDark ? '#64748b' : '#6b7280' }}>置信度</span>
            <span
              className="font-medium"
              style={{
                color: edge.strength >= 0.85 ? '#16a34a' : edge.strength >= 0.7 ? '#ca8a04' : '#dc2626',
                fontWeight: 600,
                fontSize: '16px'
              }}
            >
              {(edge.strength * 100).toFixed(0)}%
            </span>
          </div>
          <div className="flex flex-col text-center" style={{ ...cardStyle }}>
            <span className="mb-2" style={{ color: isDark ? '#64748b' : '#6b7280' }}>推荐JOIN</span>
            <span className="font-medium" style={{ color: isDark ? '#e2e8f0' : '#374151' }}>
              {edge.join_type || 'INNER JOIN'}
            </span>
          </div>
        </div>

        {/* 关系描述 */}
        {edge.business_relation && (edge.business_relation.relation_description || edge.business_relation.from_role || edge.business_relation.to_role) && (
          <div
            style={{
              backgroundColor: isDark ? 'rgba(99, 102, 241, 0.15)' : '#eef2ff',
              borderRadius: '12px',
              padding: '14px',
              marginBottom: '16px'
            }}
          >
            <div className="text-xs font-medium mb-2" style={{ color: isDark ? '#a5b4fc' : '#4f46e5' }}>
              业务关系
            </div>
            <div className="text-sm" style={{ color: isDark ? '#e2e8f0' : '#374151', lineHeight: 1.6 }}>
              {edge.business_relation.relation_description}
            </div>
            <div className="flex gap-4 mt-3 text-xs" style={{ color: isDark ? '#64748b' : '#6b7280' }}>
              {edge.business_relation.from_role && (
                <span>源角色: <strong style={{ color: isDark ? '#a5b4fc' : '#4f46e5' }}>{edge.business_relation.from_role}</strong></span>
              )}
              {edge.business_relation.to_role && (
                <span>目标角色: <strong style={{ color: isDark ? '#a5b4fc' : '#4f46e5' }}>{edge.business_relation.to_role}</strong></span>
              )}
            </div>
          </div>
        )}

        {/* JOIN 条件 */}
        {edge.join_condition && (
          <div style={{ marginBottom: '16px' }}>
            <div className="text-xs font-medium mb-2" style={{ color: isDark ? '#e2e8f0' : '#374151' }}>
              JOIN 条件
            </div>
            <div
              className="font-mono text-xs"
              style={{
                backgroundColor: '#1f2937',
                color: '#4ade80',
                borderRadius: '12px',
                padding: '14px',
                fontFamily: 'monospace',
                lineHeight: 1.6
              }}
            >
              {edge.join_condition}
            </div>
          </div>
        )}

        {/* 字段映射 */}
        {edge.join_conditions && edge.join_conditions.length > 0 && (
          <div style={{ marginBottom: '16px' }}>
            <div className="text-xs font-medium mb-2" style={{ color: isDark ? '#e2e8f0' : '#374151' }}>
              字段映射 ({edge.join_conditions.length})
            </div>
            <div className="space-y-2">
              {edge.join_conditions.map((cond, idx) => (
                <div
                  key={idx}
                  className="flex items-center text-xs"
                  style={{ ...cardStyle }}
                >
                  <span className="font-mono flex-1 truncate" style={{ color: '#3b82f6' }}>{cond.local_field}</span>
                  <span className="mx-3" style={{ color: isDark ? '#475569' : '#d1d5db' }}>=</span>
                  <span className="font-mono flex-1 truncate" style={{ color: '#22c55e' }}>{cond.remote_field}</span>
                  {cond.relationship_type && (
                    <span
                      className="ml-2 text-[10px]"
                      style={{
                        backgroundColor: isDark ? '#1e293b' : '#f1f5f9',
                        color: isDark ? '#64748b' : '#6b7280',
                        ...tagStyle
                      }}
                    >
                      {RELATIONSHIP_TYPE_LABELS[cond.relationship_type]?.label || cond.relationship_type}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SQL 示例 */}
        {edge.join_sql && (
          <div style={{ marginBottom: '16px' }}>
            <div className="text-xs font-medium mb-2" style={{ color: isDark ? '#e2e8f0' : '#374151' }}>
              SQL 示例
            </div>
            <pre
              className="text-xs overflow-x-auto whitespace-pre-wrap"
              style={{
                backgroundColor: '#1f2937',
                color: '#4ade80',
                borderRadius: '12px',
                padding: '14px',
                fontFamily: 'monospace',
                margin: 0,
                lineHeight: 1.6
              }}
            >
              {edge.join_sql}
            </pre>
          </div>
        )}

        {/* 融合策略 */}
        {edge.fusion_suggestion && (edge.fusion_suggestion.primary_table || edge.fusion_suggestion.secondary_table || edge.fusion_suggestion.aggregation_hint || edge.fusion_suggestion.fusion_strategy) && (
          <div
            style={{
              backgroundColor: isDark ? 'rgba(34, 197, 94, 0.15)' : '#f0fdf4',
              borderRadius: '12px',
              padding: '14px',
              marginBottom: '16px'
            }}
          >
            <div className="text-xs font-medium mb-2" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>
              融合建议
            </div>
            {edge.fusion_suggestion.primary_table && (
              <div className="text-xs mb-1.5" style={{ color: isDark ? '#e2e8f0' : '#374151' }}>
                <strong>主表:</strong> {edge.fusion_suggestion.primary_table}
              </div>
            )}
            {edge.fusion_suggestion.secondary_table && (
              <div className="text-xs mb-1.5" style={{ color: isDark ? '#e2e8f0' : '#374151' }}>
                <strong>从表:</strong> {edge.fusion_suggestion.secondary_table}
              </div>
            )}
            {edge.fusion_suggestion.aggregation_hint && (
              <div className="text-xs mb-1.5" style={{ color: isDark ? '#e2e8f0' : '#374151' }}>
                <strong>聚合提示:</strong> {edge.fusion_suggestion.aggregation_hint}
              </div>
            )}
            {edge.fusion_suggestion.fusion_strategy && (
              <div className="text-xs" style={{ color: isDark ? '#e2e8f0' : '#374151' }}>
                <strong>融合策略:</strong> {edge.fusion_suggestion.fusion_strategy}
              </div>
            )}
          </div>
        )}

        {/* 使用场景 */}
        {edge.use_cases && edge.use_cases.length > 0 && edge.use_cases.some(uc => uc && uc.trim()) && (
          <div style={{ marginBottom: '16px' }}>
            <div className="text-xs font-medium mb-2" style={{ color: isDark ? '#e2e8f0' : '#374151' }}>
              使用场景
            </div>
            <div className="space-y-2">
              {edge.use_cases.map((useCase, idx) => (
                <div
                  key={idx}
                  className="text-xs"
                  style={{ ...cardStyle, color: isDark ? '#e2e8f0' : '#374151' }}
                >
                  {useCase}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 底部提示 */}
        <div
          className="text-center text-[10px] pt-3"
          style={{
            color: isDark ? '#475569' : '#9ca3af',
            borderTop: `1px solid ${isDark ? '#334155' : '#e5e7eb'}`
          }}
        >
          点击空白处关闭 · 双击重置视图
        </div>
      </div>
    </div>
  )
}

// ============ 辅助函数 ============
function pointToLineDistance(px: number, py: number, x1: number, y1: number, x2: number, y2: number): number {
  const dx = x2 - x1
  const dy = y2 - y1
  const len2 = dx * dx + dy * dy

  if (len2 === 0) return Math.sqrt((px - x1) ** 2 + (py - y1) ** 2)

  let t = ((px - x1) * dx + (py - y1) * dy) / len2
  t = Math.max(0, Math.min(1, t))

  const nearX = x1 + t * dx
  const nearY = y1 + t * dy

  return Math.sqrt((px - nearX) ** 2 + (py - nearY) ** 2)
}

function lightenColor(hex: string, percent: number): string {
  const num = parseInt(hex.replace('#', ''), 16)
  const amt = Math.round(2.55 * percent)
  const R = Math.min(255, (num >> 16) + amt)
  const G = Math.min(255, ((num >> 8) & 0x00FF) + amt)
  const B = Math.min(255, (num & 0x0000FF) + amt)
  return `rgb(${R},${G},${B})`
}
