import OverviewPage from './Overview';
import type { Props } from './type';

export default function Page({ params: { lng } }: Props) {
  return <OverviewPage lng={lng} />;
}
