import * as ScrollArea from "@radix-ui/react-scroll-area"
import React, { type ReactNode } from "react"
import "./Aside.scss"

export type AsideContentItem = {
  title: string
  scrollable: boolean
  canvas?: false | boolean
  content?: React.ReactNode
}

const Header = ({children} : {children: string | ReactNode}) => <h1 className="aside-title">{children}</h1>

const AsideContent = ({ contents }: { contents: AsideContentItem[] }) => {
  const SectionTitle = ({ text }: { text: string }) => (
    <div className="section-title">
      <h3>{text}</h3>
    </div>
  )

  const SectionContent = ({
    scrollable,
    children,
  }: {
    scrollable: boolean
    children: React.ReactNode
  }) => {
    if (!scrollable) return <div className="section-content">{children}</div>

    

    return (
      <ScrollArea.Root className="scroll-wrapper">
        <ScrollArea.Viewport className="scroll-viewport">
          {children}
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar className="scrollbar" orientation="vertical">
          <ScrollArea.Thumb className="scroll-thumb" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>
    )
  }

  return (
    <div className="aside-section">
      {contents.map((content, i) => (
        <div className="section-block" key={i}>
          <SectionTitle text={content.title} />
          <SectionContent scrollable={content.scrollable}>
            {content.content}
          </SectionContent>
        </div>
      ))}
    </div>
  )
}

const Aside = ({ header, children }: { header: string, children: React.ReactNode }) => {
  return (
    <div className="aside-root">
      <Header>{header}</Header>
      <ScrollArea.Root className="scroll-wrapper">
        <ScrollArea.Viewport className="scroll-viewport">
          {children}
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar className="scrollbar" orientation="vertical">
          <ScrollArea.Thumb className="scroll-thumb" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>
    </div>
  )
}

const AsideRoot = Aside
const AsideSection = AsideContent

export default {
  AsideRoot,
  AsideSection,
}
