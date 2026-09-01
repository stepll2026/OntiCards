'use client'
import React, { useEffect, useState } from 'react'
import { Spin } from 'antd'
import { createPortal } from 'react-dom'
export default function Loading() {
  const [loadingNode, setLoadingNode] = useState(null)
  useEffect(() => {
    setLoadingNode(createPortal(<div className='z-999 fixed top-0 left-0 w-full h-full flex justify-center items-center bg-white/[0.6] '>
      <Spin tip='Loading...' size='large'>
        <div className='bg-black shadow  p-[50px] rounded-[8px]'></div>
      </Spin>
    </div>, document.getElementById('root')))
  }, [])
  return loadingNode && loadingNode
}
