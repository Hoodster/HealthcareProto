import './App.css'
import MasterDetail from '@components/MasterDetail'
import Aside from './Aside'

function App() {
  return (
    <>
    <MasterDetail
    masterView={<Aside.AsideRoot header='Assistant'><Aside.AsideSection contents={[{title: 'Patient History', scrollable: true,}]}></Aside.AsideSection></Aside.AsideRoot>}
    detailView={<h3>Blah blah</h3>}/>
    </>
  )
}

export default App
