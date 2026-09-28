type BrowserLocation = Pick<Location, 'href' | 'search' | 'hash'>

const fragmentParams = (hash: string) => new URLSearchParams(hash.replace(/^#/, ''))

export const getSSOAccessToken = (location: BrowserLocation): string | null => {
  const fragmentToken = fragmentParams(location.hash).get('access_token')
  if (fragmentToken)
    return fragmentToken

  // Keep accepting the legacy query form during rolling upgrades.
  return new URLSearchParams(location.search).get('access_token')
}

export const hasSSOAccessToken = (location: BrowserLocation): boolean =>
  getSSOAccessToken(location) !== null

export const urlWithoutSSOAccessToken = (location: BrowserLocation): string => {
  const url = new URL(location.href)
  url.searchParams.delete('access_token')

  const params = fragmentParams(url.hash)
  params.delete('access_token')
  const fragment = params.toString()

  return `${url.pathname}${url.search}${fragment ? `#${fragment}` : ''}`
}
