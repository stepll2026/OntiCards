import LoginPage from './LoginPage';
import type { Props } from './type';

export default function Page({ params: { lng } }: Props) {
  return <LoginPage lng={lng} />;
}
