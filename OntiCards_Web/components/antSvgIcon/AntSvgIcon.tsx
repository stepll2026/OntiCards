'use client'
import Icon from '@ant-design/icons'
import styles from './AntSvgIcon.module.scss'
import Historical from '@/public/iconSvg/historical.svg'
import Apps from '@/public/iconSvg/apps.svg'
import Dataset from '@/public/iconSvg/dataset.svg'
import Notice from '@/public/iconSvg/notice.svg'
import UserGroup from '@/public/iconSvg/userGroup.svg'
import Audio from '@/public/iconSvg/audio.svg'
import Picture from '@/public/iconSvg/picture.svg'
import Sending from '@/public/iconSvg/sending.svg'
import Exit from '@/public/iconSvg/exit.svg'
import Lng from '@/public/iconSvg/lng.svg'
import Lock from '@/public/iconSvg/lock.svg'
import User from '@/public/iconSvg/user.svg'
import Configuration from '@/public/iconSvg/configuration.svg'
import AudioFiles from '@/public/iconSvg/audioFiles.svg'
import HtmlFiles from '@/public/iconSvg/htmlFiles.svg'
import Answer from '@/public/iconSvg/answer.svg'
import Source from '@/public/iconSvg/source.svg'
import Question from '@/public/iconSvg/question.svg'
import Return from '@/public/iconSvg/return.svg'
import LockLine from '@/public/iconSvg/lock_line.svg'
import Warning from '@/public/iconSvg/warning.svg'
import RightArrow from '@/public/iconSvg/rightArrow.svg'
import Workflow from '@/public/iconSvg/workflow.svg'
import Preview from '@/public/iconSvg/preview.svg'
import Result from '@/public/iconSvg/result.svg'
import News from '@/public/iconSvg/news.svg'
import AiPicture from '@/public/iconSvg/AiPicture.svg'
import Examine from '@/public/iconSvg/examine.svg'
import Illustration from '@/public/iconSvg/illustration.svg'
import AddFile from '@/public/iconSvg/addFile.svg'
import AddFolder from '@/public/iconSvg/addFolder.svg'
import NewIcon from '@/public/iconSvg/new_icon.svg'
import Target from '@/public/iconSvg/target.svg'
import Save from '@/public/iconSvg/save.svg'
import File from '@/public/iconSvg/file.svg'
import Net from '@/public/iconSvg/net.svg'
import DatasetSource from '@/public/iconSvg/datasetSource.svg'
import Edit from '@/public/iconSvg/edit.svg'
import SolutionExamine from '@/public/iconSvg/solution_examine.svg'
import SolutionPicture from '@/public/iconSvg/solution_picture.svg'
import SolutionSetup from '@/public/iconSvg/solution_setup.svg'
import SolutionWrite from '@/public/iconSvg/solution_write.svg'
import SolutionMedia from '@/public/iconSvg/solution_media.svg'
import Analysis from '@/public/iconSvg/analysis.svg'
import GBIAnalysis from '@/public/iconSvg/GBI_analysis.svg'
import Query from '@/public/iconSvg/query.svg'
import Insight from '@/public/iconSvg/insight.svg'
import Chart from '@/public/iconSvg/chart.svg'
import Retailers from '@/public/iconSvg/retailers.svg'
import HottopicWriter from '@/public/iconSvg/HottopicWriter.svg'
import Report from '@/public/iconSvg/report.svg'
import RetailersAnalysis from '@/public/iconSvg/retailers_analysis.svg'
import Reptile from '@/public/iconSvg/reptile.svg'
import Chapter from '@/public/iconSvg/chapter.svg'
import Outline from '@/public/iconSvg/outline.svg'
import Textbook from '@/public/iconSvg/textbook.svg'
import TextbookPPT from '@/public/iconSvg/textbook_PPT.svg'
import Monitor from '@/public/iconSvg/monitor.svg'
import SecureIdentification from '@/public/iconSvg/secure_identification.svg'
import Train from '@/public/iconSvg/train.svg'
import PCB from '@/public/iconSvg/PCB.svg'
import OCR from '@/public/iconSvg/OCR.svg'
import PCBAnalysis from '@/public/iconSvg/PCB_analysis.svg'
import Structural from '@/public/iconSvg/structural.svg'
import Solution from '@/public/iconSvg/solution.svg'

type iconType =
  | 'chapter'
  | 'solution'
  | 'outline'
  | 'monitor'
  | 'train'
  | 'PCB'
  | 'OCR'
  | 'PCBAnalysis'
  | 'structural'
  | 'secureIdentification'
  | 'textbook'
  | 'textbookPPT'
  | 'report'
  | 'reptile'
  | 'retailersAnalysis'
  | 'HottopicWriter'
  | 'retailers'
  | 'chart'
  | 'GBIAnalysis'
  | 'analysis'
  | 'query'
  | 'insight'
  | 'solutionMedia'
  | 'solutionWrite'
  | 'solutionSetup'
  | 'solutionExamine'
  | 'solutionPicture'
  | 'edit'
  | 'file'
  | 'net'
  | 'datasetSource'
  | 'save'
  | 'target'
  | 'new_icon'
  | 'addFile'
  | 'addFolder'
  | 'illustration'
  | 'aiPicture'
  | 'examine'
  | 'news'
  | 'result'
  | 'preview'
  | 'workflow'
  | 'rightArrow'
  | 'warning'
  | 'lock_line'
  | 'return'
  | 'question'
  | 'source'
  | 'answer'
  | 'htmlFiles'
  | 'audioFiles'
  | 'configuration'
  | 'historical'
  | 'apps'
  | 'dataset'
  | 'notice'
  | 'userGroup'
  | 'audio'
  | 'picture'
  | 'sending'
  | 'lng'
  | 'lock'
  | 'exit'
  | 'user'
export default function AntSvgIcon({
  type,
  className,
  style,
  iconBoxStyle,
}: {
  type: iconType
  className?: string
  style?: React.CSSProperties
  iconBoxStyle?: React.CSSProperties
}) {
  const Icons = {
    historical: Historical,
    apps: Apps,
    dataset: Dataset,
    notice: Notice,
    userGroup: UserGroup,
    audio: Audio,
    picture: Picture,
    sending: Sending,
    lng: Lng,
    lock: Lock,
    exit: Exit,
    user: User,
    configuration: Configuration,
    audioFiles: AudioFiles,
    htmlFiles: HtmlFiles,
    answer: Answer,
    source: Source,
    question: Question,
    return: Return,
    lock_line: LockLine,
    warning: Warning,
    workflow: Workflow,
    rightArrow: RightArrow,
    preview: Preview,
    result: Result,
    news: News,
    aiPicture: AiPicture,
    examine: Examine,
    illustration: Illustration,
    addFile: AddFile,
    addFolder: AddFolder,
    new_icon: NewIcon,
    target: Target,
    save: Save,
    file: File,
    net: Net,
    datasetSource: DatasetSource,
    edit: Edit,
    solutionExamine: SolutionExamine,
    solutionPicture: SolutionPicture,
    solutionSetup: SolutionSetup,
    solutionWrite: SolutionWrite,
    solutionMedia: SolutionMedia,
    analysis: Analysis,
    GBIAnalysis,
    query: Query,
    insight: Insight,
    chart: Chart,
    retailers: Retailers,
    HottopicWriter,
    report: Report,
    retailersAnalysis: RetailersAnalysis,
    reptile: Reptile,
    chapter: Chapter,
    outline: Outline,
    textbook: Textbook,
    textbookPPT: TextbookPPT,
    monitor: Monitor,
    secureIdentification: SecureIdentification,
    train: Train,
    PCB,
    OCR,
    PCBAnalysis,
    structural: Structural,
    solution: Solution,
  }[type]

  return (
    Icons && (
      <Icon
        style={iconBoxStyle}
        className={className}
        component={() => <Icons style={style} className={styles.icon_box} fill={'currentcolor'} height={'1em'} width={'1em'}></Icons>}
      />
    )
  )
}
