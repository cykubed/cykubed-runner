context('another test context', () => {

  beforeEach( ()=> {
    cy.visit('/');
  });

  it('this test will pass - jolly good', () => {
    cy.get('h1').should('contain.text', 'Dummy');
  });
});
