import SettingsPage from './SettingsPage';
import type { Props } from './type';

export default function Page({ params }: Props) {
  return <SettingsPage lng={params.lng} />;
}
