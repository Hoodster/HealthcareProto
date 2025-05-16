import type { ReactNode } from "react";
import styles from './MasterDetail.module.scss'
import { Separator } from "radix-ui";

interface MasterDetailProps {
    masterView: ReactNode
    detailView: ReactNode
}

function MasterDetail(props: MasterDetailProps): React.ReactNode {
    return (
    <div className={styles['master-detail']}>
        <div className={styles['master-view']}>{props.masterView}</div>
        <Separator.Root orientation='vertical' decorative style={{margin: '15px 0', background: 'white'}}/>
        <div className={styles['detail-view']}>{props.detailView}</div>
    </div>);
}

export default MasterDetail