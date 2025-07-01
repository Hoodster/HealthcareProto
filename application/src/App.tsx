import './App.css'
import MasterDetail from './components/master-detail/MasterDetail'
import Aside from './Aside'
import Header from './components/header/Header'
import Footer from './components/footer/Footer'

function App() {

  const Item = ({name, ...props}: {name: string}) => {
    return <div className='listitem' {...props}>
      {name}
    </div>
  }

  return (
    <>
    <Header/>
    <MasterDetail
    masterView={
    <Aside.AsideRoot header='Assistant'>
      <Aside.AsideSection contents={[
        { 
          title: 'Patient History', 
          scrollable: true, 
          content: Array(7).fill("John Shadowdoubt").map((e,i) => {
              return (
                <Item key={i} name={e}/>
              )})
        }
      ]}>
        </Aside.AsideSection></Aside.AsideRoot>}
    detailView={<h3>Blah blah</h3>}/>
    <Footer/>
    </>
  )
}

export default App
