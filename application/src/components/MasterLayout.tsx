import { Outlet } from "react-router";

function MasterLayout({text} : {text: string}) {

    const TitleBox = () => {
        return (<div><h3>{text ?? 'Test'}</h3></div>)
    }

    return (
        <div>
            <TitleBox/>
            <Outlet/>
        </div>
    )
}

export default MasterLayout