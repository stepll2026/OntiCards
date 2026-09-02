import Link from 'next/link'

const Home = async ({ params }: { params: Promise<{ lng: string }> }) => {
  const { lng } = await params
  return (
    <div>
      <Link href={`/${lng}/overview`}>🚀</Link>
    </div>
  )
}

export default Home
