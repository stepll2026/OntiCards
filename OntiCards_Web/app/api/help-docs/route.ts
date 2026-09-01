import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const doc = searchParams.get('doc')

    let fileName = ''
    if (doc === 'quickstart') {
      fileName = '快速开始.md'
    } else if (doc === 'product') {
      fileName = '说明文档.md'
    } else {
      return NextResponse.json({ error: '文档不存在' }, { status: 404 })
    }

    const filePath = path.join(process.cwd(), 'docs', fileName)
    const content = fs.readFileSync(filePath, 'utf-8')

    return NextResponse.json({ content })
  } catch (error) {
    console.error('读取文档失败:', error)
    return NextResponse.json({ error: '读取文档失败' }, { status: 500 })
  }
}

