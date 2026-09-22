'use client'

import React, { useEffect, useLayoutEffect, useRef, useState, useMemo, useCallback } from 'react'
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
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
  isPinned?: boolean
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
export default function RelationshipGraph({ data, relationshipCards }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const simulationRef = useRef<d3.Simulation<SimNode, SimEdge> | null>(null)

  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })
  const [isDark, setIsDark] = useState(false)
  const [selectedEdge, setSelectedEdge] = useState<SimEdge | null>(null)
  const [isSimRunning, setIsSimRunning] = useState(false)
  const [pinnedCount, setPinnedCount] = useState(0)
  const [isFullscreen, setIsFullscreen] = useState(false)
  // 节点数量档位 - 默认 100% (全部)
  const [tierPercent, setTierPercent] = useState(100)
  // 图谱是否已完成首次渲染 - 用于控制加载提示
  const [isGraphInitialized, setIsGraphInitialized] = useState(false)

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
  const isNodeDraggingRef = useRef(false)
  const dataInitializedRef = useRef(false)
  // 图谱是否已首次渲染 - 用 ref 避免在 tick 内触发额外重建
  const isGraphInitializedRef = useRef(false)
  const dimensionsRef = useRef(dimensions)
  // 仅在数据(节点总数)真正改变时才重新初始化模拟,避免无关操作重置
  const dataKeyRef = useRef<string>('')
  // 仅在初次加载/数据变化时自动适应视图一次,防止莫名重置
  const hasInitialFitRef = useRef(false)
  // 渲染脏标记: 避免每帧都全量重绘,只在节点位置实际变化时渲染
  const needsRenderRef = useRef(false)
  // 追踪上一帧节点位置,用于判断是否需要重绘
  const lastNodePositionsRef = useRef<Map<string, [number, number]>>(new Map())

  // 同步 dimensions 到 ref
  useEffect(() => {
    dimensionsRef.current = dimensions
  }, [dimensions])

  // 关键修复: dimensions 变化时(例如容器尺寸重测、窗口尺寸变化)主动重绘一次
  // 原因: 当 React 重渲染 canvas 时(width/height 属性被重设),整个 canvas 内容会被清空
  // 此时 simulation 虽然还在 tick,但为了避免用户感知到空白,立即同步重绘一次
  useLayoutEffect(() => {
    if (simulationRef.current && nodesRef.current.length > 0) {
      try {
        renderRef.current()
      } catch (e) {
        // 初次挂载时可能 doRender 还没准备好
        console.warn('[dimensions 变化重绘失败]:', e)
      }
    }
  }, [dimensions])

  // 同步 selectedEdge 到 ref(doRender 需读取)
  useEffect(() => {
    selectedEdgeRef.current = selectedEdge
  }, [selectedEdge])

  // 同步 isDark 到 ref
  useEffect(() => {
    isDarkRef.current = isDark
  }, [isDark])

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

  // 智能档位配置 - 根据总节点数动态生成档位(小数据集也提供选项)
  const tierConfig = useMemo(() => {
    if (!data?.nodes.length) return []
    const total = data.nodes.length
    // 始终至少提供 2 个档位,确保按钮可见
    let percentages: number[]
    if (total <= 6) {
      percentages = [100, 50]  // 8 节点以下,提供 100/50 两个选项
    } else if (total <= 15) {
      percentages = [100, 50, 25]
    } else if (total <= 40) {
      percentages = [100, 50, 25]
    } else if (total <= 100) {
      percentages = [100, 50, 25, 10]
    } else if (total <= 250) {
      percentages = [100, 75, 50, 25]
    } else {
      percentages = [100, 75, 50, 25, 10]
    }
    return percentages.map(p => ({
      percent: p,
      count: Math.max(2, Math.ceil(total * p / 100))
    }))
  }, [data?.nodes.length])

  // 过滤后的数据 - 按 related_count 降序,只取 Top N
  const filteredData = useMemo(() => {
    if (!data) return null
    if (tierPercent === 100 || !data.nodes.length) return data

    // 按相关度(连接数)降序排序,优先保留核心节点
    const sorted = [...data.nodes].sort((a, b) => {
      const da = (a.related_count || 0) + (a.datasource_id ? 0.1 : 0)
      const db = (b.related_count || 0) + (b.datasource_id ? 0.1 : 0)
      return db - da
    })
    const count = Math.max(2, Math.ceil(data.nodes.length * tierPercent / 100))
    const visibleNodes = sorted.slice(0, count)
    const visibleIds = new Set(visibleNodes.map(n => n.id))

    // 边: 只保留两端节点都在显示集合中的边
    const visibleEdges = data.edges.filter(e =>
      visibleIds.has(e.source) && visibleIds.has(e.target)
    )

    return { nodes: visibleNodes, edges: visibleEdges }
  }, [data, tierPercent])

  // 当档位变化时,重置 hasInitialFit 以触发新的适应视图
  useEffect(() => {
    hasInitialFitRef.current = false
  }, [tierPercent])

  const hasMultipleDatasources = datasourceColorMap.size > 1

  // 计算自适应节点半径和布局参数
  const layoutConfig = useMemo(() => {
    const nodeCount = data?.nodes.length || 0
    const edgeCount = data?.edges.length || 0
    const totalElements = nodeCount + edgeCount

    // 根据数据规模调整参数
    let radius: number
    let linkDistance: number
    let chargeStrength: number
    let collisionRadius: number
    let edgeWidth: number
    let showLabels: boolean
    let showEdgeLabels: boolean
    let showArrows: boolean
    let showNodeLabels: boolean

    if (totalElements > 3000) {
      // 超大规模：极简渲染
      radius = 8
      linkDistance = 90
      chargeStrength = -380
      collisionRadius = 22
      edgeWidth = 0.6
      showLabels = false
      showEdgeLabels = false
      showArrows = false
      showNodeLabels = false
    } else if (totalElements > 1500) {
      // 大规模
      radius = 11
      linkDistance = 110
      chargeStrength = -550
      collisionRadius = 28
      edgeWidth = 0.9
      showLabels = true
      showEdgeLabels = false
      showArrows = true
      showNodeLabels = true
    } else if (totalElements > 500) {
      // 中等规模
      radius = 15
      linkDistance = 140
      chargeStrength = -750
      collisionRadius = 34
      edgeWidth = 1.2
      showLabels = true
      showEdgeLabels = false
      showArrows = true
      showNodeLabels = true
    } else if (totalElements > 100) {
      // 小规模
      radius = 19
      linkDistance = 170
      chargeStrength = -950
      collisionRadius = 40
      edgeWidth = 1.5
      showLabels = true
      showEdgeLabels = true
      showArrows = true
      showNodeLabels = true
    } else {
      // 正常规模
      radius = 24
      linkDistance = 200
      chargeStrength = -1200
      collisionRadius = 48
      edgeWidth = 1.8
      showLabels = true
      showEdgeLabels = true
      showArrows = true
      showNodeLabels = true
    }

    return {
      radius,
      linkDistance,
      chargeStrength,
      collisionRadius,
      edgeWidth,
      showLabels,
      showEdgeLabels,
      showArrows,
      showNodeLabels
    }
  }, [data?.nodes.length, data?.edges.length])

  // 给 doRender 提供最新值引用(避免闭包陈旧,同时减少 doRender 重建)
  const layoutConfigRef = useRef(layoutConfig)
  const dataScaleLevelRef = useRef(dataScaleLevel)
  const selectedEdgeRef = useRef(selectedEdge)
  const isDarkRef = useRef(isDark)

  // 同步 layoutConfig / dataScaleLevel 到 ref
  useEffect(() => {
    layoutConfigRef.current = layoutConfig
  }, [layoutConfig])

  useEffect(() => {
    dataScaleLevelRef.current = dataScaleLevel
  }, [dataScaleLevel])

  // 深色模式
  useEffect(() => {
    const checkDark = () => setIsDark(document.documentElement.getAttribute('data-theme') === 'dark')
    checkDark()
    const observer = new MutationObserver(checkDark)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  // 容器尺寸
  useEffect(() => {
    let mounted = true
    let timeoutIds: NodeJS.Timeout[] = []

    const updateDimensions = () => {
      if (!mounted || !containerRef.current) return

      const container = containerRef.current
      const rect = container.getBoundingClientRect()

      let width = rect.width
      let height = rect.height

      if (width === 0 || height === 0 || isFullscreen) {
        // 全屏模式: 直接使用视口尺寸
        // canvas 在容器内 top:56,高度 = viewport - 56(留出顶部工具栏空间)
        width = rect.width || window.innerWidth
        height = isFullscreen ? (window.innerHeight - 56) : window.innerHeight
      }

      width = Math.max(width, 400)
      height = Math.max(height, 300)

      setDimensions({ width, height })

      if (canvasRef.current) {
        canvasRef.current.width = width
        canvasRef.current.height = height
      }
    }

    timeoutIds.push(setTimeout(() => { if (mounted) updateDimensions() }, 0))
    timeoutIds.push(setTimeout(() => { if (mounted) updateDimensions() }, 100))
    timeoutIds.push(setTimeout(() => { if (mounted) updateDimensions() }, 300))

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
  }, [isFullscreen])

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
    // 用 ref 读取最新 dimensions - 全屏切换时坐标转换仍然正确
    const { width, height } = dimensionsRef.current
    return {
      x: (screenX - width / 2 - tx) / k,
      y: (screenY - height / 2 - ty) / k
    }
  }, [])

  // ============ 网格背景渲染 ============
  const drawGrid = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number, k: number) => {
    const { x: tx, y: ty } = transformRef.current
    const gridSize = 60
    const minorGridSize = 12

    // 仅在缩放合适时绘制网格
    if (k < 0.3) return

    // 计算当前视口在图谱坐标中的范围
    const left = (-width / 2 - tx) / k
    const top = (-height / 2 - ty) / k
    const right = (width / 2 - tx) / k
    const bottom = (height / 2 - ty) / k

    // 计算次网格线密度
    const minorVisible = minorGridSize * k >= 4
    const majorVisible = gridSize * k >= 6

    const gridColor = isDark
      ? (k > 1.5 ? 'rgba(99, 102, 241, 0.12)' : 'rgba(99, 102, 241, 0.08)')
      : (k > 1.5 ? 'rgba(99, 102, 241, 0.15)' : 'rgba(99, 102, 241, 0.08)')

    ctx.save()
    ctx.lineWidth = 1 / k

    // 次网格线
    if (minorVisible) {
      ctx.strokeStyle = gridColor
      ctx.beginPath()
      const startX = Math.floor(left / minorGridSize) * minorGridSize
      const endX = Math.ceil(right / minorGridSize) * minorGridSize
      const startY = Math.floor(top / minorGridSize) * minorGridSize
      const endY = Math.ceil(bottom / minorGridSize) * minorGridSize

      for (let x = startX; x <= endX; x += minorGridSize) {
        ctx.moveTo(x, top)
        ctx.lineTo(x, bottom)
      }
      for (let y = startY; y <= endY; y += minorGridSize) {
        ctx.moveTo(left, y)
        ctx.lineTo(right, y)
      }
      ctx.stroke()
    }

    // 主网格线
    if (majorVisible) {
      ctx.strokeStyle = isDarkRef.current ? 'rgba(99, 102, 241, 0.22)' : 'rgba(99, 102, 241, 0.2)'
      ctx.beginPath()
      const startX = Math.floor(left / gridSize) * gridSize
      const endX = Math.ceil(right / gridSize) * gridSize
      const startY = Math.floor(top / gridSize) * gridSize
      const endY = Math.ceil(bottom / gridSize) * gridSize

      for (let x = startX; x <= endX; x += gridSize) {
        ctx.moveTo(x, top)
        ctx.lineTo(x, bottom)
      }
      for (let y = startY; y <= endY; y += gridSize) {
        ctx.moveTo(left, y)
        ctx.lineTo(right, y)
      }
      ctx.stroke()
    }

    // 绘制原点十字线（更明显）
    if (k > 0.4) {
      const originColor = isDarkRef.current ? 'rgba(244, 114, 182, 0.4)' : 'rgba(244, 114, 182, 0.35)'
      ctx.strokeStyle = originColor
      ctx.lineWidth = 1.5 / k
      ctx.beginPath()
      ctx.moveTo(-2000, 0)
      ctx.lineTo(2000, 0)
      ctx.moveTo(0, -2000)
      ctx.lineTo(0, 2000)
      ctx.stroke()
    }

    ctx.restore()
  }, [])

  // ============ Canvas 渲染函数 ============
  // 性能优化: 使用 ref 读取最新值,避免依赖变化导致整个函数重建(影响拖动流畅度)
  const doRender = useCallback(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return

    // 全部通过 ref 读取最新值 - 这样 doRender 不会因 dimensions/layoutConfig 变化而重建
    const { width, height } = dimensionsRef.current
    const { x: tx, y: ty, k } = transformRef.current
    const config = layoutConfigRef.current
    const r = config.radius * Math.max(0.35, Math.min(1.3, k))
    const isDarkVal = isDarkRef.current

    // 背景 - 渐变
    if (isDarkVal) {
      const bgGrad = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, Math.max(width, height) * 0.7)
      bgGrad.addColorStop(0, '#1e293b')
      bgGrad.addColorStop(1, '#0f172a')
      ctx.fillStyle = bgGrad
    } else {
      const bgGrad = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, Math.max(width, height) * 0.7)
      bgGrad.addColorStop(0, '#fafbfc')
      bgGrad.addColorStop(1, '#eef2f7')
      ctx.fillStyle = bgGrad
    }
    ctx.fillRect(0, 0, width, height)

    // 应用变换
    ctx.save()
    ctx.translate(width / 2 + tx, height / 2 + ty)
    ctx.scale(k, k)

    // 先绘制网格
    drawGrid(ctx, width, height, k)

    const hovered = hoveredEdgeRef.current
    const selected = selectedEdgeRef.current
    const nodes = nodesRef.current
    const edges = edgesRef.current

    // ============ 绘制边 ============
    if (dataScaleLevelRef.current === 'extreme') {
      // 极简模式
      edges.forEach(edge => {
        // 关键修复: 跳过 source 或 target 为 undefined 的孤儿边,防止崩溃
        if (!edge.source || !edge.target) return
        const sx = edge.source.x
        const sy = edge.source.y
        const tx2 = edge.target.x
        const ty2 = edge.target.y

        const dx = tx2 - sx
        const dy = ty2 - sy
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist === 0 || dist > 800) return

        ctx.beginPath()
        ctx.moveTo(sx, sy)
        ctx.lineTo(tx2, ty2)
        ctx.strokeStyle = getEdgeColor(edge)
        ctx.lineWidth = 0.5
        ctx.globalAlpha = 0.25
        ctx.stroke()
        ctx.globalAlpha = 1
      })
    } else {
      // 普通模式 - 双层绘制(底层阴影 + 上层)
      edges.forEach(edge => {
        // 关键修复: 跳过 source 或 target 为 undefined 的孤儿边,防止崩溃
        if (!edge.source || !edge.target) return
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
        const isHighlighted = isHovered || isSelected

        ctx.beginPath()
        ctx.moveTo(startX, startY)
        ctx.lineTo(endX, endY)
        ctx.strokeStyle = getEdgeColor(edge)
        ctx.lineWidth = isHighlighted ? config.edgeWidth * 2.5 : config.edgeWidth
        ctx.globalAlpha = isHighlighted ? 1 : 0.55

        if (edge.is_cross_source) {
          ctx.setLineDash([8, 5])
        } else {
          ctx.setLineDash([])
        }
        ctx.stroke()
        ctx.setLineDash([])
        ctx.globalAlpha = 1

        // 箭头
        if (config.showArrows && r >= 8) {
          const arrowSize = Math.max(5, r * 0.45)
          const arrowAngle = Math.atan2(dy, dx)
          const color = getEdgeColor(edge)
          ctx.fillStyle = color
          ctx.globalAlpha = isHighlighted ? 1 : 0.75
          ctx.beginPath()
          ctx.moveTo(endX, endY)
          ctx.lineTo(
            endX - arrowSize * Math.cos(arrowAngle - Math.PI / 6),
            endY - arrowSize * Math.sin(arrowAngle - Math.PI / 6)
          )
          ctx.lineTo(
            endX - arrowSize * Math.cos(arrowAngle + Math.PI / 6),
            endY - arrowSize * Math.sin(arrowAngle + Math.PI / 6)
          )
          ctx.closePath()
          ctx.fill()
          ctx.globalAlpha = 1
        }

        // 边标签（仅小规模）
        if (config.showEdgeLabels && nodes.length <= PERF.LOW && r >= 12 && (isHighlighted || dist < 220)) {
          const midX = (startX + endX) / 2
          const midY = (startY + endY) / 2
          const cardinality = CARDINALITY_LABELS[edge.cardinality] || ''
          const typeLabel = RELATIONSHIP_TYPE_LABELS[edge.label]?.label || ''
          const text = [cardinality, typeLabel].filter(Boolean).join(' ')

          if (text) {
            const fontSize = Math.max(9, Math.min(11, r * 0.42))
            ctx.font = `bold ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
            const metrics = ctx.measureText(text)
            const padding = 4
            const bgWidth = metrics.width + padding * 2
            const bgHeight = fontSize + padding * 2
            const edgeColor = getEdgeColor(edge)

            ctx.fillStyle = isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)'
            ctx.beginPath()
            if (ctx.roundRect) {
              ctx.roundRect(midX - bgWidth / 2, midY - bgHeight / 2, bgWidth, bgHeight, 4)
            } else {
              ctx.rect(midX - bgWidth / 2, midY - bgHeight / 2, bgWidth, bgHeight)
            }
            ctx.fill()

            // 边框
            ctx.strokeStyle = edgeColor
            ctx.lineWidth = 1
            ctx.stroke()

            ctx.fillStyle = edgeColor
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.fillText(text, midX, midY)
          }
        }
      })
    }

    // 高亮悬停/选中的边
    if (hovered || selected) {
      const highlightEdge = hovered || selected
      // 关键修复: 仅在 source/target 都有效时绘制高亮,避免孤儿边渲染崩溃
      if (highlightEdge.source && highlightEdge.target) {
        ctx.beginPath()
        ctx.moveTo(highlightEdge.source.x, highlightEdge.source.y)
        ctx.lineTo(highlightEdge.target.x, highlightEdge.target.y)
        ctx.strokeStyle = getEdgeColor(highlightEdge)
        ctx.lineWidth = config.edgeWidth * 3
        ctx.globalAlpha = 0.3
        ctx.stroke()
        ctx.globalAlpha = 1
      }
    }

    // ============ 绘制节点 ============
    nodes.forEach(node => {
      const color = getNodeColor(node)
      const isDraggedNode = draggedNodeRef.current === node
      const isPinned = node.isPinned

      // 外发光(拖动节点或锁定节点)
      if (isDraggedNode || isPinned) {
        ctx.shadowColor = isDraggedNode ? color : 'rgba(82, 196, 26, 0.6)'
        ctx.shadowBlur = isDraggedNode ? 18 : 12
      }

      // 节点阴影
      ctx.shadowColor = 'rgba(0, 0, 0, 0.25)'
      ctx.shadowBlur = 6
      ctx.shadowOffsetY = 2

      // 节点主体 - 径向渐变
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
      const gradient = ctx.createRadialGradient(
        node.x - r * 0.35, node.y - r * 0.35, 0,
        node.x, node.y, r
      )
      gradient.addColorStop(0, lightenColor(color, 35))
      gradient.addColorStop(0.6, color)
      gradient.addColorStop(1, darkenColor(color, 12))
      ctx.fillStyle = gradient
      ctx.fill()

      // 重置阴影
      ctx.shadowColor = 'transparent'
      ctx.shadowBlur = 0
      ctx.shadowOffsetY = 0

      // 节点边框
      ctx.strokeStyle = isDraggedNode
        ? '#ffffff'
        : isPinned
          ? '#52c41a'
          : 'rgba(255, 255, 255, 0.5)'
      ctx.lineWidth = isDraggedNode || isPinned ? 2.5 : 1.5
      ctx.stroke()

      // 锁定标记 - 一个小圆点
      if (isPinned && r > 10) {
        ctx.beginPath()
        ctx.arc(node.x + r * 0.7, node.y - r * 0.7, Math.max(2.5, r * 0.15), 0, Math.PI * 2)
        ctx.fillStyle = '#52c41a'
        ctx.strokeStyle = '#ffffff'
        ctx.lineWidth = 1
        ctx.fill()
        ctx.stroke()
      }

      // 节点标签
      if (config.showNodeLabels) {
        const tableName = node.label || node.id
        const displayName = tableName.length > 6 ? tableName.substring(0, 5) + '..' : tableName
        const fontSize = Math.max(8, Math.min(11, r * 0.4))

        // 标签背景(提高可读性)
        ctx.font = `bold ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
        const metrics = ctx.measureText(displayName)
        const labelPadding = 3
        const labelW = metrics.width + labelPadding * 2
        const labelH = fontSize + labelPadding
        const labelY = node.y + r + labelH * 0.7

        ctx.fillStyle = isDarkRef.current ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.9)'
        ctx.beginPath()
        if (ctx.roundRect) {
          ctx.roundRect(node.x - labelW / 2, labelY - labelH / 2, labelW, labelH, 3)
        } else {
          ctx.rect(node.x - labelW / 2, labelY - labelH / 2, labelW, labelH)
        }
        ctx.fill()

        ctx.fillStyle = isDarkRef.current ? '#e2e8f0' : '#1f2937'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(displayName, node.x, labelY)
      }
    })

    ctx.restore()
  }, [getNodeColor, getEdgeColor, drawGrid])

  // 保存 render 函数引用 - 使用 useLayoutEffect 确保在浏览器首次绘制前同步设置
  useLayoutEffect(() => {
    renderRef.current = doRender
  }, [doRender])

  // 检测悬停边
  const detectHoveredEdge = useCallback((screenX: number, screenY: number) => {
    if (dataScaleLevelRef.current === 'extreme') return null

    const graphPos = screenToGraph(screenX, screenY)
    const hitRadius = 14 / Math.max(0.4, transformRef.current.k)

    const selected = selectedEdgeRef.current
    if (selected && selected.source && selected.target) {
      const dist = pointToLineDistance(
        graphPos.x, graphPos.y,
        selected.source.x, selected.source.y,
        selected.target.x, selected.target.y
      )
      if (dist < hitRadius) return selected
    }

    for (const edge of edgesRef.current) {
      if (edge === selected) continue
      // 关键修复: 跳过 source 或 target 为 undefined 的孤儿边,防止点击/悬停时崩溃
      if (!edge.source || !edge.target) continue
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
  }, [screenToGraph])

  // 检测点击的节点
  const detectNode = useCallback((screenX: number, screenY: number) => {
    const graphPos = screenToGraph(screenX, screenY)
    const hitRadius = Math.max(layoutConfigRef.current.radius * 1.8, 18)

    for (const node of nodesRef.current) {
      const dx = node.x - graphPos.x
      const dy = node.y - graphPos.y
      if (Math.sqrt(dx * dx + dy * dy) < hitRadius) {
        return node
      }
    }
    return null
  }, [screenToGraph])

  // 从卡片数据中查找边详情
  const findEdgeDetails = useCallback((sourceId: string, targetId: string): SimEdge | null => {
    const cards = relationshipCardsRef.current || []
    const sourceTableName = sourceId
    const targetTableName = targetId

    // 关键修复: 先确认两个节点都存在于当前可见节点集合中,否则返回 null
    // 避免返回 source/target 为 undefined 的边对象,导致 EdgeDetailPanel 渲染时报错
    const sourceNode = nodesRef.current.find(n => n.id === sourceId)
    const targetNode = nodesRef.current.find(n => n.id === targetId)
    if (!sourceNode || !targetNode) return null

    const sourceCard = cards.find(card => card.table_name === sourceTableName)
    const targetCard = cards.find(card => card.table_name === targetTableName)

    if (sourceCard?.card?.Relationships) {
      const relationship = sourceCard.card.Relationships.find(
        rel => rel.related_table === targetTableName
      )
      if (relationship) {
        return {
          source: sourceNode,
          target: targetNode,
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
          source: targetNode,
          target: sourceNode,
          label: 'Semantic',
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

  // ============ 适应视图 ============
  const fitToView = useCallback((animate = true) => {
    const nodes = nodesRef.current
    if (nodes.length === 0) return

    // 使用 ref 读取最新 dimensions - 全屏切换时也能正确适应
    const { width, height } = dimensionsRef.current
    const padding = 100

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    nodes.forEach(n => {
      if (n.x < minX) minX = n.x
      if (n.x > maxX) maxX = n.x
      if (n.y < minY) minY = n.y
      if (n.y > maxY) maxY = n.y
    })

    const graphWidth = Math.max(maxX - minX, 100)
    const graphHeight = Math.max(maxY - minY, 100)
    const availableWidth = width - padding * 2
    const availableHeight = height - padding * 2

    const scale = Math.min(
      availableWidth / graphWidth,
      availableHeight / graphHeight,
      1.5
    )
    const finalScale = Math.max(0.2, Math.min(2.5, scale))

    const centerX = (minX + maxX) / 2
    const centerY = (minY + maxY) / 2

    // 目标变换:让 graph 中心对齐到画布中心
    const targetTx = -centerX * finalScale
    const targetTy = -centerY * finalScale

    if (animate) {
      const startTx = transformRef.current.x
      const startTy = transformRef.current.y
      const startK = transformRef.current.k
      const duration = 600
      const startTime = performance.now()

      const animateFrame = (now: number) => {
        const elapsed = now - startTime
        const t = Math.min(1, elapsed / duration)
        // 缓动函数
        const ease = t < 0.5
          ? 2 * t * t
          : 1 - Math.pow(-2 * t + 2, 2) / 2

        transformRef.current = {
          x: startTx + (targetTx - startTx) * ease,
          y: startTy + (targetTy - startTy) * ease,
          k: startK + (finalScale - startK) * ease
        }
        renderRef.current()

        if (t < 1) {
          requestAnimationFrame(animateFrame)
        }
      }
      requestAnimationFrame(animateFrame)
    } else {
      transformRef.current = { x: targetTx, y: targetTy, k: finalScale }
      renderRef.current()
    }

    initialScaleRef.current = finalScale
  }, [])

  // ============ 初始化模拟 ============
  const initSimulation = useCallback(() => {
    const sourceData = filteredData || data
    if (!sourceData?.nodes.length) return

    // 计算数据指纹,仅当数据实际变化时重新初始化(防止莫名重置)
    const dataKey = `${sourceData.nodes.length}_${sourceData.edges.length}_${tierPercent}`
    if (dataKey === dataKeyRef.current && simulationRef.current) {
      return
    }

    // 停止旧模拟
    if (simulationRef.current) {
      simulationRef.current.stop()
    }

    // 关键修复: 用 dimensionsRef.current 而非 dimensions state,避免 dimensions 变化触发整个 initSimulation
    // (dimensions 变化时只需要重新 render 即可,不应 stop simulation 造成图谱消失)
    const { width, height } = dimensionsRef.current || dimensions
    const centerX = 0
    const centerY = 0

    // ============ 改进: 真正均匀分散的初始布局 ============
    // 基于 Halton 序列的拟随机分布 - 让节点在画布上均匀散开,没有任何聚拢倾向
    // 散布半径扩大,确保覆盖整个画布可视区域
    const baseSpread = Math.min(width, height) * 0.7

    // 用于追踪每个节点的度数(连接数)
    const nodeDegree = new Map<string, number>()
    sourceData.edges.forEach(e => {
      nodeDegree.set(e.source, (nodeDegree.get(e.source) || 0) + 1)
      nodeDegree.set(e.target, (nodeDegree.get(e.target) || 0) + 1)
    })

    // Halton 序列 - 低差异拟随机分布,比黄金角分布更均匀
    const halton = (index: number, base: number) => {
      let result = 0
      let f = 1 / base
      let i = index
      while (i > 0) {
        result += f * (i % base)
        i = Math.floor(i / base)
        f = f / base
      }
      return result
    }

    nodesRef.current = sourceData.nodes.map((n, i) => {
      // 使用 Halton 序列(2,3 素数底)生成均匀分布的归一化坐标 [0, 1]
      const u = halton(i + 1, 2)
      const v = halton(i + 1, 3)
      // 映射到 [-baseSpread, baseSpread] 区间,确保覆盖整个画布
      const x = (u - 0.5) * 2 * baseSpread
      const y = (v - 0.5) * 2 * baseSpread

      return {
        ...n,
        x,
        y,
        vx: 0,
        vy: 0
      }
    })

    const nodeMap = new Map(nodesRef.current.map(n => [n.id, n]))
    edgesRef.current = sourceData.edges
      .map((e): SimEdge | null => {
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
      // 关键修复: 过滤掉任何 source/target 缺失或缺失坐标(x/y)的孤儿边,
      // 避免后续绘制 / 悬停 / 点击 / EdgeDetailPanel 渲染时崩溃
      .filter((e): e is SimEdge =>
        e !== null &&
        !!e.source && !!e.target &&
        Number.isFinite(e.source.x) && Number.isFinite(e.source.y) &&
        Number.isFinite(e.target.x) && Number.isFinite(e.target.y)
      )

    hoveredEdgeRef.current = null
    setPinnedCount(0)

    // 重置图谱初始化标志 - 重新显示加载提示,直到第一次 tick 渲染完成
    isGraphInitializedRef.current = false
    setIsGraphInitialized(false)

    // ============ 改进: 更合理的力学参数(中心力减弱,完全自由分布) ============
    const config = layoutConfig
    const simulation = d3.forceSimulation<SimNode>(nodesRef.current)
      .force('link', d3.forceLink<SimNode, SimEdge>(edgesRef.current)
        .id(d => d.id)
        .distance((d) => {
          const baseDist = config.linkDistance
          return baseDist * (0.85 + (1 - d.strength) * 0.4)
        })
        .strength((d) => {
          return 0.15 + d.strength * 0.5
        }))
      .force('charge', d3.forceManyBody()
        .strength(config.chargeStrength)
        .distanceMin(40)
        .distanceMax(Math.max(500, config.linkDistance * 4)))
      // 极弱中心力 - 允许节点自由分散,不再强制拉回中心
      .force('center', d3.forceCenter(centerX, centerY).strength(0.015))
      .force('collision', d3.forceCollide<SimNode>()
        .radius((d) => config.collisionRadius)
        .strength(0.85))
      // 极弱的边界约束 - 让图谱自由分布,而不是被强拉回中心
      // 强度为 0 意味着完全不约束,完全由初始位置和力主导
      .force('x', d3.forceX(0).strength(0))
      .force('y', d3.forceY(0).strength(0))

    // 调节 alpha - 让模拟有充分的时间展现运动过程
    if (dataScaleLevel === 'extreme') {
      simulation.alpha(0.6).alphaDecay(0.025)
    } else if (dataScaleLevel === 'high') {
      simulation.alpha(0.8).alphaDecay(0.02)
    } else if (dataScaleLevel === 'medium') {
      simulation.alpha(1).alphaDecay(0.018)
    } else {
      simulation.alpha(1).alphaDecay(0.015)
    }

    // 速度衰减适中 - 让节点移动更流畅,不会突然卡顿
    simulation.velocityDecay(0.35)

    simulationRef.current = simulation
    setIsSimRunning(true)

    // 初始缩放
    initialScaleRef.current = 1
    transformRef.current = { x: 0, y: 0, k: 1 }
    // 重置渲染脏标记 - 初始化时设为 true 确保首次渲染
    needsRenderRef.current = true
    lastNodePositionsRef.current = new Map()

    // ============ 改进: 同步立即绘制初始帧 ============
    // 不再依赖第一次 tick 触发渲染 - 这样避免 React 状态更新与 simulation 回调之间的时序竞态
    // (某些情况下 setIsGraphInitialized 会触发重渲染,使 canvas width/height 被 React 重设而清空内容)
    // 在 initSimulation 末尾同步调用 renderRef.current(),确保用户能立即看到图谱
    try {
      // 同步绘制初始帧 - 此时节点已有初始坐标
      renderRef.current()
      needsRenderRef.current = false
      // 关闭加载提示 - 让初始帧立刻可见
      if (!isGraphInitializedRef.current) {
        isGraphInitializedRef.current = true
        setIsGraphInitialized(true)
      }
    } catch (e) {
      // 出错时不影响后续 simulation tick
      console.warn('[initSimulation] 初始帧渲染失败:', e)
    }

    // 用于节流 pinnedCount 更新的计数器
    let pinnedUpdateCounter = 0

    simulation.on('tick', () => {
      // 更新节点位置记录(用于后续可能的优化)
      const nodes = nodesRef.current
      for (const node of nodes) {
        lastNodePositionsRef.current.set(node.id, [node.x, node.y])
      }

      // 关键修复: 始终渲染 - 因为节点在力学模拟中持续移动
      renderRef.current()
      needsRenderRef.current = false

      // 首次渲染后立即关闭加载提示,避免空白等待
      if (!isGraphInitializedRef.current) {
        isGraphInitializedRef.current = true
        setIsGraphInitialized(true)
      }

      // pinnedCount 更新节流:每 30 帧更新一次,避免每帧触发 re-render
      pinnedUpdateCounter++
      if (pinnedUpdateCounter >= 30) {
        pinnedUpdateCounter = 0
        let count = 0
        nodesRef.current.forEach(n => { if (n.isPinned) count++ })
        setPinnedCount(count)
      }

      // 当模拟接近稳定时自动适应视图(只触发一次,看到运动过程后再适配)
      if (!hasInitialFitRef.current && simulation.alpha() < 0.08) {
        hasInitialFitRef.current = true
        fitToView(true)  // 启用平滑动画
      }
    })

    simulation.on('end', () => {
      setIsSimRunning(false)
      // 关键修复: 不再自动 fitToView - 用户已多次反馈"莫名被重置视图"
      // 只在真正需要时(初次加载/用户点击)才适应视图
      renderRef.current()
    })

    // 更新数据指纹
    dataKeyRef.current = dataKey
    dataInitializedRef.current = true
    // 适应视图移到了 simulation.on('tick') 里,在 alpha < 0.08 时自动触发,
    // 这样用户能看到从初始均匀分散 -> 力学收敛的运动过程
    // 关键修复: 不再依赖 dimensions,避免窗口尺寸变化时整个 simulation 重建导致图谱消失
  }, [filteredData, layoutConfig, dataScaleLevel, fitToView])

  // 触发模拟初始化 - 使用 useLayoutEffect 确保在浏览器首次绘制前同步执行
  // 这样初次加载时 canvas 就能立即显示初始帧,避免出现"空白等待一会才显示"的问题
  useLayoutEffect(() => {
    initSimulation()
    return () => {
      if (simulationRef.current) {
        simulationRef.current.stop()
      }
    }
  }, [initSimulation])

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
      // 拖动时设置 fx/fy,这样节点不会因为力被拉走
      clickedNode.fx = clickedNode.x
      clickedNode.fy = clickedNode.y
      // 短暂提高 alpha 让其他节点平滑响应
      simulationRef.current?.alphaTarget(0.2).restart()
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
      // 让 simulation 重启以驱动其他节点响应,但 alphaTarget 限制能量避免过度震荡
      if (simulationRef.current) {
        simulationRef.current.alphaTarget(0.1).restart()
        // 立即调用一次 render,确保节点跟手流畅(否则要等下一个 tick)
        renderRef.current()
      }
    } else if (isDraggingRef.current === 'canvas') {
      const dx = x - dragStartRef.current.x
      const dy = y - dragStartRef.current.y
      const distance = Math.sqrt(dx * dx + dy * dy)
      dragDistanceRef.current = distance

      if (distance > 5) {
        hasDraggedRef.current = true
        transformRef.current = {
          ...transformRef.current,
          x: dragStartRef.current.tx + dx,
          y: dragStartRef.current.ty + dy
        }
        // 画布拖动直接 render 即可,不需要 simulation
        renderRef.current()
      }
    } else {
      // 悬停检测 - 用 RAF 节流,避免每个 mousemove 都触发
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      rafRef.current = requestAnimationFrame(() => {
        const hovered = detectHoveredEdge(x, y)
        if (hovered !== hoveredEdgeRef.current) {
          hoveredEdgeRef.current = hovered
          renderRef.current()
          // 改变鼠标样式
          if (canvasRef.current) {
            canvasRef.current.style.cursor = hovered ? 'pointer' : 'grab'
          }
        }
      })
    }
  }, [screenToGraph, detectHoveredEdge])

  const handleMouseUp = useCallback((e?: React.MouseEvent) => {
    const wasDragging = isDraggingRef.current
    const wasDraggingNode = wasDragging === 'node' && draggedNodeRef.current

    if (wasDraggingNode) {
      const node = draggedNodeRef.current!
      // 关键修复: 拖动后**保持**节点固定位置(用户期望的行为)
      // 通过 fx/fy 维持位置
      if (!hasDraggedRef.current) {
        // 没有拖动(只是点击),立即释放
        node.fx = null
        node.fy = null
      } else {
        // 拖动后保持固定,标记为 pinned
        node.isPinned = true
        node.fx = node.x
        node.fy = node.y
      }
      simulationRef.current?.alphaTarget(0)
    }

    hasDraggedRef.current = false
    dragDistanceRef.current = 0
    isDraggingRef.current = null
    draggedNodeRef.current = null

    if (wasDragging === 'canvas') {
      renderRef.current()
    }
  }, [])

  const handleClick = useCallback((e: React.MouseEvent) => {
    if (isNodeDraggingRef.current) {
      isNodeDraggingRef.current = false
      return
    }

    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    if (detectNode(x, y)) return

    const clickedEdge = detectHoveredEdge(x, y)
    if (clickedEdge) {
      // 关键修复: 当 source/target 不完整时,跳过查找详情,直接展示原始 edge 信息
      // 这样即使 findEdgeDetails 内部判定失败,也不会把 undefined 节点传进 EdgeDetailPanel
      const enhancedEdge = (clickedEdge.source && clickedEdge.target)
        ? findEdgeDetails(clickedEdge.source.id, clickedEdge.target.id)
        : null
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

    if (selectedEdge) {
      setSelectedEdge(null)
      renderRef.current()
    }
  }, [detectNode, detectHoveredEdge, findEdgeDetails, selectedEdge])

  // 滚轮缩放
  const handleWheel = useCallback((e: WheelEvent) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    if (e.clientX < rect.left || e.clientX > rect.right ||
      e.clientY < rect.top || e.clientY > rect.bottom) {
      return
    }

    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    const delta = e.deltaY > 0 ? 0.88 : 1.14
    const newK = Math.max(0.1, Math.min(4, transformRef.current.k * delta))

    const { x, y, k } = transformRef.current
    const graphX = (mouseX - rect.width / 2 - x) / k
    const graphY = (mouseY - rect.height / 2 - y) / k
    const newX = mouseX - rect.width / 2 - graphX * newK
    const newY = mouseY - rect.height / 2 - graphY * newK

    transformRef.current = { x: newX, y: newY, k: newK }
    renderRef.current()
  }, [])

  // 使用原生事件监听器确保 preventDefault 生效
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.addEventListener('wheel', handleWheel, { passive: false })
    return () => {
      canvas.removeEventListener('wheel', handleWheel)
    }
  }, [handleWheel])

  // 双击节点 - 切换固定状态
  const handleDoubleClick = useCallback((e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const clickedNode = detectNode(x, y)

    if (clickedNode) {
      // 切换节点固定状态
      if (clickedNode.isPinned) {
        clickedNode.isPinned = false
        clickedNode.fx = null
        clickedNode.fy = null
        simulationRef.current?.alpha(0.3).restart()
      } else {
        clickedNode.isPinned = true
        clickedNode.fx = clickedNode.x
        clickedNode.fy = clickedNode.y
      }
      renderRef.current()
      return
    }

    // 双击空白处重置视图
    fitToView(true)
  }, [detectNode, fitToView])

  // 重置所有固定节点
  const unpinAll = useCallback(() => {
    nodesRef.current.forEach(n => {
      n.isPinned = false
      n.fx = null
      n.fy = null
    })
    simulationRef.current?.alpha(0.5).restart()
    setPinnedCount(0)
    renderRef.current()
  }, [])

  // 缩放控制
  const zoomBy = useCallback((factor: number) => {
    const newK = Math.max(0.1, Math.min(4, transformRef.current.k * factor))
    const k = transformRef.current.k
    // 以画布中心为缩放原点
    const targetX = 0
    const targetY = 0
    const graphX = (targetX - transformRef.current.x) / k
    const graphY = (targetY - transformRef.current.y) / k
    const newX = targetX - graphX * newK
    const newY = targetY - graphY * newK

    transformRef.current = { x: newX, y: newY, k: newK }
    renderRef.current()
  }, [])

  // 切换全屏 - 同时重新适应视图
  const toggleFullscreen = useCallback(() => {
    setIsFullscreen(prev => {
      const next = !prev
      // 全屏状态切换后,让视图重新适应
      if (next || prev) {
        // 延迟到 DOM 更新后执行,确保 dimensions 已更新
        requestAnimationFrame(() => {
          setTimeout(() => fitToView(false), 50)
        })
      }
      return next
    })
  }, [fitToView])

  // 监听 ESC 退出全屏
  useEffect(() => {
    if (!isFullscreen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsFullscreen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [isFullscreen])

  // 切换档位 - 用户点击档位按钮时调用
  const switchTier = useCallback((percent: number) => {
    if (percent === tierPercent) return
    // 切换档位时清理选中状态,避免高亮的"孤儿边"残留(指向已不在 nodesRef.current 中的旧节点)
    setSelectedEdge(null)
    hoveredEdgeRef.current = null
    selectedEdgeRef.current = null
    setTierPercent(percent)
  }, [tierPercent])

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

  const buttonStyle: React.CSSProperties = {
    backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
    backdropFilter: 'blur(12px)',
    border: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`,
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
    borderRadius: '10px',
    width: '36px',
    height: '36px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    transition: 'all 0.2s',
    color: isDark ? '#cbd5e1' : '#475569'
  }

  return (
    <>
      <div
        ref={containerRef}
        className="relative w-full overflow-hidden"
        style={{
          position: isFullscreen ? 'fixed' : 'relative',
          top: isFullscreen ? 0 : 'auto',
          left: isFullscreen ? 0 : 'auto',
          right: isFullscreen ? 0 : 'auto',
          bottom: isFullscreen ? 0 : 'auto',
          width: isFullscreen ? '100vw' : '100%',
          height: isFullscreen ? '100vh' : '100%',
          minHeight: isFullscreen ? 0 : '400px',
          zIndex: isFullscreen ? 9999 : 'auto',
          backgroundColor: isFullscreen ? (isDark ? '#0f172a' : '#fafbfc') : 'transparent',
          animation: isFullscreen ? 'fullscreenFadeIn 0.25s ease-out' : 'none'
        }}
      >
        {/* 全屏模式顶部工具栏 - 最高层级,确保不被其他元素遮挡 */}
        {isFullscreen && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 200,  // 最高层级
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 20px',
            borderBottom: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.4)' : 'rgba(226, 232, 240, 0.8)'}`,
            backgroundColor: isDark ? 'rgba(15, 23, 42, 0.85)' : 'rgba(255, 255, 255, 0.85)',
            backdropFilter: 'blur(12px)'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '14px',
              fontSize: '15px',
              fontWeight: 600,
              color: isDark ? '#e2e8f0' : '#1f2937'
            }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <circle cx="6" cy="6" r="2.5" stroke="#3b82f6" strokeWidth="2" />
                <circle cx="18" cy="6" r="2.5" stroke="#52c41a" strokeWidth="2" />
                <circle cx="12" cy="18" r="2.5" stroke="#722ed1" strokeWidth="2" />
                <line x1="7.5" y1="7" x2="17" y2="6.5" stroke="#94a3b8" strokeWidth="1.2" />
                <line x1="7" y1="7" x2="11" y2="16.5" stroke="#94a3b8" strokeWidth="1.2" />
                <line x1="17" y1="7" x2="13" y2="16.5" stroke="#94a3b8" strokeWidth="1.2" />
              </svg>
              <span>关系图谱 · 全屏模式</span>
              {filteredData && (
                <span style={{
                  fontSize: '12px',
                  fontWeight: 400,
                  color: isDark ? '#94a3b8' : '#6b7280',
                  marginLeft: '8px'
                }}>
                当前显示 <strong style={{ color: '#3b82f6' }}>{filteredData.nodes.length}</strong> 节点 / <strong style={{ color: '#22c55e' }}>{filteredData.edges.length}</strong> 边
                  {tierPercent < 100 && data && ` (共 ${data.nodes.length})`}
              </span>
              )}
            </div>
            <button
              onClick={() => setIsFullscreen(false)}
              title="退出全屏 (ESC)"
              style={{
                ...buttonStyle,
                backgroundColor: isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(241, 245, 249, 1)',
                border: 'none'
              }}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        )}
        {/* 状态指示器 */}
        {isSimRunning && (
          <div style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
            color: 'white',
            fontSize: '12px',
            padding: '8px 16px',
            borderRadius: '20px',
            zIndex: 20,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 8px 24px rgba(59, 130, 246, 0.4)'
          }}>
          <span style={{
            width: '8px',
            height: '8px',
            backgroundColor: 'white',
            borderRadius: '50%',
            animation: 'pulse 1.5s infinite'
          }}></span>
            智能布局中...
          </div>
        )}

        {/* 统计信息 */}
        <div style={{
          position: 'absolute',
          top: isFullscreen ? '72px' : '16px',  // 全屏模式下向下偏移,避开标题栏
          left: '16px',
          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(12px)',
          borderRadius: '20px',
          padding: '12px 20px',
          zIndex: 100,  // 高于 canvas,低于顶部工具栏
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)',
          border: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`,
          fontSize: '13px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ color: '#3b82f6', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#3b82f6' }}></span>
            <span style={{ fontWeight: 700, fontSize: '15px' }}>{filteredData?.nodes.length ?? data.nodes.length}</span>
            <span>节点</span>
            {tierPercent < 100 && filteredData && (
              <span style={{ fontSize: '11px', color: isDark ? '#64748b' : '#9ca3af', fontWeight: 400 }}>
                / {data.nodes.length}
              </span>
            )}
          </span>
            <span style={{ color: '#22c55e', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <svg width="16" height="16" viewBox="0 0 16 16">
              <line x1="2" y1="8" x2="14" y2="8" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <span style={{ fontWeight: 700, fontSize: '15px' }}>{filteredData?.edges.length ?? data.edges.length}</span>
            <span>边</span>
              {tierPercent < 100 && filteredData && (
                <span style={{ fontSize: '11px', color: isDark ? '#64748b' : '#9ca3af', fontWeight: 400 }}>
                / {data.edges.length}
              </span>
              )}
          </span>
            {pinnedCount > 0 && (
              <span style={{ color: '#52c41a', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
                <path d="M6 0l1.5 3.5L11 4l-2.5 2.5L9 10 6 8l-3 2 .5-3.5L1 4l3.5-.5L6 0z" />
              </svg>
              <span style={{ fontWeight: 700, fontSize: '15px' }}>{pinnedCount}</span>
              <span>已固定</span>
            </span>
            )}
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

        {/* 缩放控制按钮 */}
        <div style={{
          position: 'absolute',
          top: isFullscreen ? '72px' : '16px',  // 全屏模式下向下偏移,避开标题栏
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 100,  // 高于 canvas,低于顶部工具栏
          display: 'flex',
          gap: '6px',
          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(12px)',
          border: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`,
          borderRadius: '24px',
          padding: '6px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)'
        }}>
          <button
            style={buttonStyle}
            onClick={() => zoomBy(0.8)}
            title="缩小"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? '#475569' : '#f1f5f9'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <line x1="3" y1="8" x2="13" y2="8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
          <button
            style={{ ...buttonStyle, width: 'auto', padding: '0 14px', fontSize: '12px', fontWeight: 600 }}
            onClick={() => fitToView(true)}
            title="适应视图"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? '#475569' : '#f1f5f9'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)'
            }}
          >
            {Math.round(transformRef.current.k * 100)}%
          </button>
          <button
            style={buttonStyle}
            onClick={() => zoomBy(1.25)}
            title="放大"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? '#475569' : '#f1f5f9'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <line x1="3" y1="8" x2="13" y2="8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <line x1="8" y1="3" x2="8" y2="13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
          <div style={{ width: '1px', backgroundColor: isDark ? '#475569' : '#e2e8f0', margin: '6px 2px' }} />
          <button
            style={buttonStyle}
            onClick={() => fitToView(true)}
            title="适应视图"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? '#475569' : '#f1f5f9'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)'
            }}
          >
            {/* 适应视图图标 - 取景框样式(与全屏箭头图标区分) */}
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="2" y="2" width="12" height="12" rx="1" stroke="currentColor" strokeWidth="1.5" />
              <rect x="5" y="5" width="6" height="6" rx="0.5" fill="currentColor" opacity="0.5" />
            </svg>
          </button>
          <button
            style={buttonStyle}
            onClick={unpinAll}
            title="释放所有固定节点"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? '#475569' : '#f1f5f9'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.5" />
              <path d="M8 1v2M8 13v2M1 8h2M13 8h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          <div style={{ width: '1px', backgroundColor: isDark ? '#475569' : '#e2e8f0', margin: '6px 2px' }} />
          {/* 全屏按钮 */}
          <button
            style={buttonStyle}
            onClick={toggleFullscreen}
            title="全屏展示"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? '#475569' : '#f1f5f9'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)'
            }}
          >
            {/* 全屏图标 - 箭头向外扩张样式,与"适应视图"的4角图标区分 */}
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M5 2H2v3M11 2h3v3M5 14H2v-3M11 14h3v-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {/* 节点数量档位切换 - 放在底部居中位置,显示区域的最下方 */}
        {tierConfig.length > 0 && (
          <div style={{
            position: 'absolute',
            bottom: '16px',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 30,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(12px)',
            border: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`,
            borderRadius: '24px',
            padding: '6px 14px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)'
          }}>
          <span style={{
            fontSize: '12px',
            fontWeight: 500,
            color: isDark ? '#94a3b8' : '#6b7280'
          }}>
            节点数量
          </span>
            <div style={{
              display: 'flex',
              gap: '2px',
              backgroundColor: isDark ? 'rgba(15, 23, 42, 0.6)' : 'rgba(241, 245, 249, 0.7)',
              borderRadius: '8px',
              padding: '3px'
            }}>
              {tierConfig.map((tier) => {
                const isActive = tier.percent === tierPercent
                return (
                  <button
                    key={tier.percent}
                    onClick={() => switchTier(tier.percent)}
                    title={`显示 Top ${tier.percent}% 节点 (${tier.count} 个)`}
                    style={{
                      background: isActive
                        ? 'linear-gradient(135deg, #3b82f6, #6366f1)'
                        : 'transparent',
                      color: isActive ? 'white' : (isDark ? '#cbd5e1' : '#475569'),
                      border: 'none',
                      borderRadius: '6px',
                      padding: '4px 12px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      minWidth: '36px'
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.backgroundColor = isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.backgroundColor = 'transparent'
                      }
                    }}
                  >
                    {tier.percent === 100 ? '全部' : `${tier.percent}%`}
                  </button>
                )
              })}
            </div>
            {tierPercent < 100 && filteredData && (
              <span style={{
                fontSize: '11px',
                color: isDark ? '#64748b' : '#9ca3af',
                fontWeight: 400,
                paddingLeft: '4px',
                borderLeft: `1px solid ${isDark ? '#475569' : '#e2e8f0'}`,
                marginLeft: '2px'
              }}>
              当前 {filteredData.nodes.length}/{data.nodes.length}
            </span>
            )}
          </div>
        )}

        {/* 图例 */}
        <div style={{
          position: 'absolute',
          bottom: '70px',
          left: '16px',
          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(12px)',
          borderRadius: '16px',
          padding: '14px 16px',
          zIndex: 20,  // 高于 canvas,确保不被 canvas 覆盖
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)',
          border: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`,
          maxWidth: '170px',
          fontSize: '12px'
        }}>
          <div style={{ fontWeight: 600, marginBottom: '10px', color: isDark ? '#e2e8f0' : '#374151' }}>图例</div>

          {!hasMultipleDatasources && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: NODE_COLORS.high, boxShadow: '0 0 6px rgba(82,196,26,0.4)' }} />
                <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>≥5 关联</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: NODE_COLORS.medium, boxShadow: '0 0 6px rgba(250,173,20,0.4)' }} />
                <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>3-4 关联</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: NODE_COLORS.default, boxShadow: '0 0 6px rgba(24,144,255,0.4)' }} />
                <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>1-2 关联</span>
              </div>
              <div style={{ borderTop: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`, margin: '8px 0' }}></div>
            </>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <div style={{ width: '20px', height: '3px', backgroundColor: EDGE_COLORS.high, borderRadius: '2px' }} />
            <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>高置信 ≥85%</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <div style={{ width: '20px', height: '3px', backgroundColor: EDGE_COLORS.medium, borderRadius: '2px' }} />
            <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>中置信 70-85%</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <div style={{ width: '20px', height: '3px', backgroundColor: EDGE_COLORS.low, borderRadius: '2px' }} />
            <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>低置信 &lt;70%</span>
          </div>

          {data.edges.some(e => e.is_cross_source) && (
            <>
              <div style={{ borderTop: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`, margin: '8px 0' }}></div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
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
          bottom: '70px',
          right: '16px',
          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(12px)',
          borderRadius: '16px',
          padding: '12px 16px',
          zIndex: 20,  // 高于 canvas,确保不被 canvas 覆盖
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)',
          border: `1px solid ${isDark ? 'rgba(71, 85, 105, 0.5)' : 'rgba(226, 232, 240, 0.8)'}`,
          fontSize: '12px',
          maxWidth: '220px'
        }}>
          <div style={{ fontWeight: 600, marginBottom: '8px', color: isDark ? '#e2e8f0' : '#374151' }}>操作提示</div>
          <div style={{ color: isDark ? '#94a3b8' : '#6b7280', lineHeight: 1.7 }}>
            <div>🖱️ 拖拽节点 <span style={{ color: '#52c41a' }}>(松手后固定)</span></div>
            <div>✋ 拖拽空白移动画布</div>
            <div>🔍 滚轮缩放视图</div>
            <div>👆 点击边查看详情</div>
            <div>👆👆 双击节点切换固定</div>
          </div>
        </div>

        {/* 图谱加载等待提示 - 在首次渲染前显示,避免空白假象 */}
        {!isGraphInitialized && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '16px',
            zIndex: 50,
            pointerEvents: 'none',  // 不拦截鼠标事件
            color: isDark ? '#e2e8f0' : '#475569'
          }}>
            {/* 双圈旋转加载动画 */}
            <div style={{ position: 'relative', width: '56px', height: '56px' }}>
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '56px',
                height: '56px',
                border: `3px solid ${isDark ? 'rgba(71, 85, 105, 0.3)' : 'rgba(226, 232, 240, 0.8)'}`,
                borderTopColor: '#3b82f6',
                borderRadius: '50%',
                animation: 'graphSpin 1s linear infinite'
              }} />
              <div style={{
                position: 'absolute',
                top: '8px',
                left: '8px',
                width: '40px',
                height: '40px',
                border: `3px solid ${isDark ? 'rgba(71, 85, 105, 0.3)' : 'rgba(226, 232, 240, 0.8)'}`,
                borderBottomColor: '#6366f1',
                borderRadius: '50%',
                animation: 'graphSpin 1.4s linear infinite reverse'
              }} />
            </div>
            <div style={{
              fontSize: '14px',
              fontWeight: 500,
              color: isDark ? '#cbd5e1' : '#64748b',
              letterSpacing: '0.3px'
            }}>
              图谱数据加载中
            </div>
          </div>
        )}

        {/* Canvas */}
        <canvas
          ref={canvasRef}
          width={dimensions.width}
          height={dimensions.height}
          style={{
            position: 'absolute',
            top: isFullscreen ? 56 : 0,
            left: 0,
            width: dimensions.width,
            height: dimensions.height,
            touchAction: 'none',
            cursor: 'grab',
            zIndex: 10  // 低于顶部工具栏(zIndex 200),让工具栏正常显示在最上层
          }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onClick={handleClick}
          onDoubleClick={handleDoubleClick}
        />

        {/* 详情面板 */}
        {selectedEdge && (
          <EdgeDetailPanel
            edge={selectedEdge}
            isDark={isDark}
            onClose={() => { setSelectedEdge(null); renderRef.current(); }}
          />
        )}

        <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes fullscreenFadeIn {
          from { opacity: 0; transform: scale(0.99); }
          to { opacity: 1; transform: scale(1); }
        }
        @keyframes graphSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
      </div>
    </>
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

  // 关键修复: 使用可选链防止 edge.source / edge.target 为 undefined 时崩溃
  // 极少数情况下(例如档位切换瞬间残留的孤儿边),edge 的两端节点可能为空,
  // 此时回退到空字符串,而不是抛出 TypeError
  const sourceName = edge.source?.label || edge.source?.id || '未知源'
  const targetName = edge.target?.label || edge.target?.id || '未知目标'

  const cardStyle: React.CSSProperties = {
    backgroundColor: isDark ? '#0f172a' : '#f8fafc',
    borderRadius: '12px',
    padding: '12px'
  }

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

function darkenColor(hex: string, percent: number): string {
  const num = parseInt(hex.replace('#', ''), 16)
  const amt = Math.round(2.55 * percent)
  const R = Math.max(0, (num >> 16) - amt)
  const G = Math.max(0, ((num >> 8) & 0x00FF) - amt)
  const B = Math.max(0, (num & 0x0000FF) - amt)
  return `rgb(${R},${G},${B})`
}
