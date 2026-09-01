import React from 'react'
import { Spin } from 'antd'
export default function Loading() {
  return <div className='w-full h-full flex justify-center items-center'>
    <Spin tip="Loading..." size="large">
      <div className='p-[50px]'></div>
    </Spin>

  </div>
}
