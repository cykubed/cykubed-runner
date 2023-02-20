context('test3', () => {

  beforeEach( ()=> {
    cy.visit('/');
  });

  it('should fail horribly', () => {
    cy.get('h2').should('contain.text', 'xxx');
  });

});
