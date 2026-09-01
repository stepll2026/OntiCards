This is a [Next.js](https://nextjs.org/) project bootstrapped with [`create-next-app`](https://github.com/vercel/next.js/tree/canary/packages/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

```angular2html
npm install react-markdown remark-math remark-breaks rehype-katex remark-gfm react-syntax-highlighter
markdown:^8.0.6  katex ^6.0.2
npm install crypto-js
npm install mermaid
react-tooltip 5.8.3
npm install use-context-selector
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `pages/index.tsx`. The page auto-updates as you edit the file.

[API routes](https://nextjs.org/docs/api-routes/introduction) can be accessed on [http://localhost:3000/api/hello](http://localhost:3000/api/hello). This endpoint can be edited in `pages/api/hello.ts`.

The `pages/api` directory is mapped to `/api/*`. Files in this directory are treated as [API routes](https://nextjs.org/docs/api-routes/introduction) instead of React pages.

This project uses [`next/font`](https://nextjs.org/docs/basic-features/font-optimization) to automatically optimize and load Inter, a custom Google Font.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js/) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/deployment) for more details.




#### **api 目录说明**

- `api` 目录主要负责后端接口的封装与调用，按功能模块划分文件，方便管理和扩展。
- `base.ts`：定义通用的基础接口逻辑，作为其他接口的基类。
- `chat.ts`：实现与聊天功能相关的 API，例如发送消息、获取聊天记录等。
- `common.ts`：封装通用的 API 工具函数，例如统一的请求处理、错误捕获等。
- `example.ts`：示例接口文件，用于测试或演示接口逻辑。
- `user.ts`：处理用户相关的 API，例如登录、注册、获取用户信息等。

------

#### **app 目录说明**

- `app` 目录主要负责应用逻辑，包括动态路由和国际化。
- `[lng]`：用于支持动态语言的路由页面文件夹，可能通过 `next.js` 的动态路由实现多语言支持。
- `i18n`：国际化文件夹，用于管理翻译资源或语言切换功能。

------

#### **components 目录说明**

- `components` 目录包含项目中的通用组件，组件化设计方便复用和维护。
- `antSvgIcon`：封装 SVG 图标组件，支持动态加载和自定义样式。
- `audioRecorder`：音频录制组件，用于实现音频采集或播放功能。
- `chatBox`：聊天框组件，封装消息展示和交互逻辑。
- `commonFileIcon`：通用文件图标组件，用于显示文件类型的图标。
- `head`：页面 `<head>` 元素管理组件，支持 SEO 优化和动态标题。
- `loading`：加载动画组件，显示加载状态。
- `login`：登录页面的组件，封装用户登录表单和交互逻辑。
- `nprogressProvider`：页面加载进度条组件，显示页面加载状态。
- `reactMarkdown`：Markdown 渲染组件，用于解析和渲染 Markdown 文本。
- `sidebar`：侧边栏组件，用于导航功能。
- `translationsProvider`：翻译功能提供组件，用于管理和切换语言。

------

#### **context 目录说明**

- `context` 目录用于管理全局状态，基于 React 的 Context API 实现。
- `homeContext.ts`：Home 页面的上下文，提供状态管理和数据共享功能。

------

#### **docker 目录说明**

- `docker` 目录存放与容器化相关的配置文件，方便项目部署。
- `entrypoint.sh`：容器的入口脚本，定义启动容器时的初始化流程。
- `pm2.json`：PM2 进程管理工具的配置文件，用于多线程或服务的运行管理。

------

#### **public 目录说明**

- `public` 是 Next.js 默认的静态资源文件夹，存放不会经过 Webpack 处理的文件。

- `iconSvg/`：SVG 图标文件夹。

- `image/`：图片资源文件夹。

- `locales/`：本地化文件夹，支持多语言切换。

- ```
  statics/
  ```

  ：静态资源文件夹，存放 favicon 和图标字体等。

  - `favicon.ico` 等：不同尺寸的 favicon 图标。
  - `iconfont.js`：图标字体文件。
  - `vercel.svg`：Vercel 平台标志。

------

#### **styles 目录说明**

- `styles` 文件夹存放项目的样式文件，包括全局样式和模块化样式。
- `animate.min.css`：动画样式库，可能来自外部资源。
- `animation.css`：自定义的动画样式文件。
- `globals.css`：全局样式文件，定义项目中的通用样式。
- `Home.module.css`：Home 页面的模块化样式文件。

------

#### **utils 目录说明**

- `utils` 目录存放工具函数，提供复用性强的通用方法。
- `index.ts`：工具函数的入口文件，统一导出工具函数。
- `utils.ts`：具体实现各种工具函数，例如格式化、数据处理等。

------

#### **根目录配置文件说明**

- `.eslintrc.json` 和 `.eslintignore`：用于配置 ESLint 规则和忽略文件，规范代码风格。
- `.prettierrc`：Prettier 配置文件，用于统一代码格式。
- `.gitignore`：Git 忽略规则，确保无关文件不会提交到版本控制。
- `.nvmrc`：Node.js 版本管理文件，指定项目依赖的 Node.js 版本。
- `Dockerfile`：定义容器镜像的构建步骤。
- `docker-compose.yaml`：用于编排多个 Docker 服务。
- `middleware.js`：中间件逻辑文件，可能包含认证或请求拦截逻辑。
- `next-env.d.ts`：Next.js 的类型声明文件。
- `next.config.js`：Next.js 的配置文件，定义项目路由、构建等行为。
- `package.json` 和 `package-lock.json`：项目依赖和脚本管理文件。
- `postcss.config.js`：PostCSS 配置文件，用于处理 CSS。
- `README.md`：项目说明文档，提供基本信息和使用说明。
- `tailwind.config.js`：TailwindCSS 配置文件，用于自定义样式。
- `tsconfig.json`：TypeScript 配置文件。
- `yarn.lock`：Yarn 的依赖锁定文件，确保依赖版本一致。

