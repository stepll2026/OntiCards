import React from 'react'
import { Spin } from 'antd'
export default function Loading() {
  return (
    <div className='flex items-cetner justify-center my-4'>
      <Spin></Spin> <div className='ml-4'>Loading...</div>
    </div>
  )
}
