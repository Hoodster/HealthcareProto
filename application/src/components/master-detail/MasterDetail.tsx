import { useEffect, useRef, useState, type ReactNode } from "react"
import styles from './MasterDetail.module.scss'
import { Separator } from "radix-ui"
import ChatInput from "../chat/ChatInput"

interface MasterDetailProps {
    masterView: ReactNode
    detailView: ReactNode
}

function DraggableArea ({children}: {children: ReactNode}){
    const containerRef = useRef<HTMLDivElement>(null)
    const [isDragging, setIsDragging] = useState(false)
    const [width, setWidth] = useState<null | number>(null)
    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (isDragging && containerRef.current) {
                const container = containerRef.current.getBoundingClientRect()
                const newWidth = e.clientX - container.left
                if (newWidth >= 200 && newWidth <= container.width - 300) {
                    setWidth(newWidth);
                }
            }
        }

        const handleMouseUp = () => setIsDragging(false)

        if (isDragging) {
            document.addEventListener('mousemove', handleMouseMove)
            document.addEventListener('mouseup', handleMouseUp)
        }

        return () => {
            document.removeEventListener('mousemove', handleMouseMove)
            document.removeEventListener('mouseup', handleMouseUp)
        }
    }, [isDragging]);

    return (<div ref={containerRef}>{children}</div>)
}

function MasterDetail(props: MasterDetailProps): React.ReactNode {
    const MAX_WIDTH = '30%';


    return (
    <div className={styles['master-detail']}>
        <div style={{height: '100%', maxWidth: MAX_WIDTH}} className={styles['master-view']}>{props.masterView}</div>
        <Separator.Root orientation='vertical' decorative style={{margin: '15px 0', background: 'white'}}/>
        <ChatInput/>
        {/* <MasterLayout className text="TEst"/> */}
        {/* <BrowserRouter>
         <Route index element={(<div className={styles['detail-view']}>{props.detailView}</div>)}/>
        </BrowserRouter> */}
    </div>);
}

export default MasterDetail